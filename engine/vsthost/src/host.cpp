// D127 (AU3): see host.h.
#include "host.h"

#include "public.sdk/source/common/memorystream.h"
#include "pluginterfaces/vst/vstspeaker.h"

#include <windows.h>

#include <algorithm>
#include <cstring>
#include <fstream>

using namespace Steinberg;
using namespace Steinberg::Vst;

namespace {
const char MAGIC[4] = {'L', '2', 'V', 'S'};

bool readBlob (std::ifstream& f, std::vector<char>& out)
{
	uint64_t n = 0;
	if (!f.read (reinterpret_cast<char*> (&n), 8) || n > (1ull << 31))
		return false;
	out.resize (size_t (n));
	return n == 0 || bool (f.read (out.data (), std::streamsize (n)));
}

void writeBlob (std::ofstream& f, const MemoryStream& s)
{
	uint64_t n = uint64_t (s.getSize ());
	f.write (reinterpret_cast<const char*> (&n), 8);
	if (n)
		f.write (s.getData (), std::streamsize (n));
}

int32 channelsOf (SpeakerArrangement a) { return SpeakerArr::getChannelCount (a); }
} // namespace

std::string utf8 (const std::wstring& w)
{
	if (w.empty ())
		return {};
	int n = WideCharToMultiByte (CP_UTF8, 0, w.data (), int (w.size ()), nullptr, 0, nullptr, nullptr);
	std::string s (size_t (n), '\0');
	WideCharToMultiByte (CP_UTF8, 0, w.data (), int (w.size ()), s.data (), n, nullptr, nullptr);
	return s;
}

std::wstring wide (const std::string& s)
{
	if (s.empty ())
		return {};
	int n = MultiByteToWideChar (CP_UTF8, 0, s.data (), int (s.size ()), nullptr, 0);
	std::wstring w (size_t (n), L'\0');
	MultiByteToWideChar (CP_UTF8, 0, s.data (), int (s.size ()), w.data (), n);
	return w;
}

std::string jstr (const std::string& s)
{
	std::string o = "\"";
	for (unsigned char c : s)
	{
		if (c == '"' || c == '\\')
			o += '\\', o += char (c);
		else if (c < 0x20)
		{
			char b[8];
			snprintf (b, sizeof (b), "\\u%04x", c);
			o += b;
		}
		else
			o += char (c);
	}
	return o + "\"";
}

Plugin::~Plugin ()
{
	teardown ();
	controller = nullptr;
	processor = nullptr;
	component = nullptr;
	provider = nullptr;
	module = nullptr;
}

bool Plugin::load (const std::string& path, const std::string& uid, std::string& err)
{
	module = VST3::Hosting::Module::create (path, err);
	if (!module)
	{
		err = "the bundle did not load: " + err;
		return false;
	}
	auto want = uid.empty () ? VST3::Optional<VST3::UID> {} : VST3::UID::fromString (uid);
	if (!uid.empty () && !want)
	{
		err = "not a class id: " + uid;
		return false;
	}
	for (auto& ci : module->getFactory ().classInfos ())
	{
		if (ci.category () != kVstAudioEffectClass || (want && ci.ID () != *want))
			continue;
		provider = owned (new PlugProvider (module->getFactory (), ci, true));
		if (!provider->initialize ())
		{
			err = "the plug-in did not initialise";
			return false;
		}
		component = provider->getComponentPtr ();
		controller = provider->getControllerPtr ();
		processor = U::cast<IAudioProcessor> (component);
		name = ci.name ();
		vendor = ci.vendor ();
		if (!processor)
		{
			err = "the plug-in processes no audio";
			return false;
		}
		return true;
	}
	err = uid.empty () ? "the bundle holds no audio effect" : "the bundle has no class " + uid;
	return false;
}

bool Plugin::loadState (const std::wstring& file, std::string& err)
{
	if (file.empty () || file == L"-")
		return true;
	std::ifstream f (file, std::ios::binary);
	char magic[4] {};
	std::vector<char> comp, ctrl;
	if (!f || !f.read (magic, 4) || std::memcmp (magic, MAGIC, 4) != 0 || !readBlob (f, comp) || !readBlob (f, ctrl))
	{
		err = "the state file cannot be read";
		return false;
	}
	if (!comp.empty ())
	{
		MemoryStream cs (comp.data (), TSize (comp.size ()));
		if (component->setState (&cs) != kResultOk)
		{
			err = "the plug-in refused its saved state";
			return false;
		}
		if (controller)
		{
			MemoryStream again (comp.data (), TSize (comp.size ()));
			controller->setComponentState (&again);
		}
	}
	if (!ctrl.empty () && controller)
	{
		MemoryStream ks (ctrl.data (), TSize (ctrl.size ()));
		controller->setState (&ks);
	}
	return true;
}

bool Plugin::saveState (const std::wstring& file, std::string& err)
{
	MemoryStream cs, ks;
	if (component->getState (&cs) != kResultOk)
	{
		err = "the plug-in gave no state";
		return false;
	}
	if (controller)
		controller->getState (&ks);
	std::wstring part = file + L".part";
	{
		std::ofstream f (part, std::ios::binary);
		f.write (MAGIC, 4);
		writeBlob (f, cs);
		writeBlob (f, ks);
		if (!f)
		{
			err = "the state file was not written";
			return false;
		}
	}
	if (!MoveFileExW (part.c_str (), file.c_str (), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
	{
		err = "the state file was not put in place";
		return false;
	}
	return true;
}

bool Plugin::setup (double sampleRate, int32_t maxBlock, std::string& err)
{
	rate = sampleRate;
	block = maxBlock;
	const int32 nIn = component->getBusCount (kAudio, kInput), nOut = component->getBusCount (kAudio, kOutput);
	if (nOut < 1)
	{
		err = "the plug-in has no audio output";
		return false;
	}
	std::vector<SpeakerArrangement> ins (size_t (nIn), SpeakerArr::kEmpty), outs (size_t (nOut), SpeakerArr::kEmpty);
	for (int32 i = 0; i < nIn; ++i)
		processor->getBusArrangement (kInput, i, ins[size_t (i)]);
	for (int32 i = 0; i < nOut; ++i)
		processor->getBusArrangement (kOutput, i, outs[size_t (i)]);
	if (nIn > 0)
		ins[0] = SpeakerArr::kStereo;
	outs[0] = SpeakerArr::kStereo;
	processor->setBusArrangements (ins.data (), nIn, outs.data (), nOut);   // a plug-in may keep its own (mono): asked again below
	if (nIn > 0)
	{
		SpeakerArrangement a = 0;
		processor->getBusArrangement (kInput, 0, a);
		inChannels = channelsOf (a);
	}
	else
		inChannels = 0;
	SpeakerArrangement o = 0;
	processor->getBusArrangement (kOutput, 0, o);
	outChannels = channelsOf (o);
	for (int32 i = 0; i < nIn; ++i)
		component->activateBus (kAudio, kInput, i, i == 0);
	for (int32 i = 0; i < nOut; ++i)
		component->activateBus (kAudio, kOutput, i, i == 0);
	for (int32 i = 0; i < component->getBusCount (kEvent, kInput); ++i)
		component->activateBus (kEvent, kInput, i, false);
	ProcessSetup ps {kOffline, kSample32, maxBlock, sampleRate};
	if (processor->setupProcessing (ps) != kResultOk)
	{
		err = "the plug-in refused offline 32-bit processing at " + std::to_string (int (sampleRate)) + " Hz";
		return false;
	}
	if (component->setActive (true) != kResultOk)
	{
		err = "the plug-in did not activate";
		return false;
	}
	active = true;
	processor->setProcessing (true);
	data.prepare (*component, maxBlock, kSample32);
	data.processMode = kOffline;
	data.inputParameterChanges = &changes;
	context = {};
	context.state = ProcessContext::kPlaying | ProcessContext::kTempoValid | ProcessContext::kTimeSigValid | ProcessContext::kContTimeValid;
	context.sampleRate = sampleRate;
	context.tempo = 120.0;
	context.timeSigNumerator = 4;
	context.timeSigDenominator = 4;
	data.processContext = &context;
	position = 0;
	return true;
}

void Plugin::teardown ()
{
	if (!active)
		return;
	processor->setProcessing (false);
	component->setActive (false);
	data.unprepare ();
	active = false;
}

void Plugin::queueParam (ParamID id, ParamValue v)
{
	pending[id] = v;
	if (controller)
		controller->setParamNormalized (id, v);
}

bool Plugin::processBlock (const float* l, const float* r, float* ol, float* or_, int32_t n)
{
	changes.clearQueue ();
	for (auto& [id, v] : pending)
	{
		int32 index = 0;
		if (auto* q = changes.addParameterData (id, index))
			q->addPoint (0, v, index);
	}
	pending.clear ();
	data.numSamples = n;
	if (data.numInputs > 0 && data.inputs[0].numChannels > 0)
	{
		auto& in = data.inputs[0];
		if (in.numChannels == 1)
			for (int32 i = 0; i < n; ++i)
				in.channelBuffers32[0][i] = 0.5f * (l[i] + r[i]);
		else
		{
			std::memcpy (in.channelBuffers32[0], l, size_t (n) * 4);
			std::memcpy (in.channelBuffers32[1], r, size_t (n) * 4);
			for (int32 c = 2; c < in.numChannels; ++c)
				std::memset (in.channelBuffers32[c], 0, size_t (n) * 4);
		}
		in.silenceFlags = 0;
	}
	context.continousTimeSamples = position;
	context.projectTimeSamples = position;
	context.projectTimeMusic = double (position) / rate * 2.0;   // quarters at 120 bpm
	if (processor->process (data) != kResultOk)
		return false;
	auto& out = data.outputs[0];
	std::memcpy (ol, out.channelBuffers32[0], size_t (n) * 4);
	std::memcpy (or_, out.channelBuffers32[out.numChannels > 1 ? 1 : 0], size_t (n) * 4);
	position += n;
	return true;
}

bool Plugin::run (Stereo& audio, int32_t& latency, std::string& err)
{
	latency = int32_t (processor->getLatencySamples ());
	const size_t n = audio.frames (), total = n + size_t (std::max (0, latency));
	std::vector<float> l (total, 0.f), r (total, 0.f), ol (total, 0.f), or_ (total, 0.f);
	std::copy (audio.l.begin (), audio.l.end (), l.begin ());
	std::copy (audio.r.begin (), audio.r.end (), r.begin ());
	for (size_t at = 0; at < total; at += size_t (block))
	{
		const int32_t m = int32_t (std::min<size_t> (size_t (block), total - at));
		if (!processBlock (&l[at], &r[at], &ol[at], &or_[at], m))
		{
			err = "the plug-in failed to process at sample " + std::to_string (at);
			return false;
		}
	}
	audio.l.assign (ol.begin () + std::max (0, latency), ol.begin () + std::max (0, latency) + std::ptrdiff_t (n));
	audio.r.assign (or_.begin () + std::max (0, latency), or_.begin () + std::max (0, latency) + std::ptrdiff_t (n));
	return true;
}
