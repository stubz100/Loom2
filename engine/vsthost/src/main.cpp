// D127 (proto01_animate 30 §16, AU3): loom2-vsthost — loom2's own VST3 host, run as a sidecar by the orchestrator (loom2/vsthost.py), one
// process per request, so a plug-in that crashes ends this process and never loom2. Every command answers one line of JSON on stdout
// ({"ok": true, …} or {"ok": false, "error": "…"}; exit code 0 / 1).
//
//   loom2-vsthost paths                                          the VST3 bundles installed in the system's folders
//   loom2-vsthost scan <bundle>                                  the bundle's audio effects (class id, name, vendor, version, sub-categories)
//   loom2-vsthost params <bundle> <uid> <state|->                an effect's parameters (id, title, units, steps, value, as shown)
//   loom2-vsthost state <bundle> <uid> <state|-> <out> [id=v…]   its state with parameters set (normalised 0…1) — tests and scripts
//   loom2-vsthost render <chain.tsv> <in.wav> <out.wav>          a WAV through a chain, offline: one line per effect, tab-separated
//                                                                <bundle> <uid> <state|-> <bypass 0|1>; each effect's latency taken off;
//                                                                a line `@gain <dB>` scales the signal there (in float: a print's gain)
//   loom2-vsthost editor <bundle> <uid> <state|-> <out> [title]  the effect's own editor in a window; its state written when it closes
#include "host.h"

#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/vst/utility/stringconvert.h"

#include <windows.h>

#include <cmath>
#include <cstdio>
#include <fstream>
#include <sstream>

using namespace Steinberg;
using namespace Steinberg::Vst;

bool runEditor (Plugin& p, const std::wstring& title, std::string& err);

namespace {
int fail (const std::string& err)
{
	std::printf ("{\"ok\": false, \"error\": %s}\n", jstr (err).c_str ());
	return 1;
}

int paths ()
{
	std::string o = "{\"ok\": true, \"paths\": [";
	bool first = true;
	for (auto& p : VST3::Hosting::Module::getModulePaths ())
	{
		o += (first ? "" : ", ") + jstr (p);
		first = false;
	}
	std::printf ("%s]}\n", o.c_str ());
	return 0;
}

int scan (const std::string& bundle)
{
	std::string err;
	auto module = VST3::Hosting::Module::create (bundle, err);
	if (!module)
		return fail ("the bundle did not load: " + err);
	std::string o = "{\"ok\": true, \"classes\": [";
	bool first = true;
	for (auto& ci : module->getFactory ().classInfos ())
	{
		if (ci.category () != kVstAudioEffectClass)
			continue;
		o += std::string (first ? "" : ", ") + "{\"uid\": " + jstr (ci.ID ().toString ()) + ", \"name\": " + jstr (ci.name ()) +
		     ", \"vendor\": " + jstr (ci.vendor ()) + ", \"version\": " + jstr (ci.version ()) + ", \"sub\": " + jstr (ci.subCategoriesString ()) + "}";
		first = false;
	}
	std::printf ("%s]}\n", o.c_str ());
	return 0;
}

int params (const std::string& bundle, const std::string& uid, const std::wstring& state)
{
	Plugin p;
	std::string err;
	if (!p.load (bundle, uid, err) || !p.loadState (state, err))
		return fail (err);
	std::string o = "{\"ok\": true, \"name\": " + jstr (p.name) + ", \"vendor\": " + jstr (p.vendor) + ", \"params\": [";
	const int32 n = p.controller ? p.controller->getParameterCount () : 0;
	for (int32 i = 0; i < n; ++i)
	{
		ParameterInfo info {};
		if (p.controller->getParameterInfo (i, info) != kResultOk)
			continue;
		const ParamValue v = p.controller->getParamNormalized (info.id);
		String128 shown {};
		p.controller->getParamStringByValue (info.id, v, shown);
		char num[64];
		std::snprintf (num, sizeof (num), "%.6g", v);
		o += std::string (i ? ", " : "") + "{\"id\": " + std::to_string (info.id) + ", \"title\": " + jstr (VST3::StringConvert::convert (info.title)) +
		     ", \"units\": " + jstr (VST3::StringConvert::convert (info.units)) + ", \"steps\": " + std::to_string (info.stepCount) + ", \"value\": " +
		     num + ", \"shown\": " + jstr (VST3::StringConvert::convert (shown)) + ", \"automatable\": " +
		     ((info.flags & ParameterInfo::kCanAutomate) ? "true" : "false") + "}";
	}
	std::printf ("%s]}\n", o.c_str ());
	return 0;
}

int state (const std::string& bundle, const std::string& uid, const std::wstring& in, const std::wstring& out, int argc, wchar_t** argv)
{
	Plugin p;
	std::string err;
	if (!p.load (bundle, uid, err) || !p.loadState (in, err) || !p.setup (48000.0, 64, err))
		return fail (err);
	for (int i = 0; i < argc; ++i)
	{
		std::string kv = utf8 (argv[i]);
		auto eq = kv.find ('=');
		if (eq == std::string::npos)
			return fail ("a parameter is id=value: " + kv);
		p.queueParam (ParamID (std::stoul (kv.substr (0, eq))), ParamValue (std::stod (kv.substr (eq + 1))));
	}
	Stereo silence;
	silence.l.assign (64, 0.f);
	silence.r.assign (64, 0.f);
	int32_t latency = 0;
	if (!p.run (silence, latency, err))
		return fail (err);
	p.teardown ();
	if (!p.saveState (out, err))
		return fail (err);
	std::printf ("{\"ok\": true, \"name\": %s}\n", jstr (p.name).c_str ());
	return 0;
}

int render (const std::wstring& chainFile, const std::wstring& inWav, const std::wstring& outWav)
{
	std::ifstream f (chainFile, std::ios::binary);
	if (!f)
		return fail ("the chain file cannot be read");
	Stereo audio;
	std::string err;
	if (!readWav (inWav, audio, err))
		return fail (err);
	std::string line, o = "{\"ok\": true, \"frames\": " + std::to_string (audio.frames ()) + ", \"rate\": " + std::to_string (int (audio.rate)) + ", \"effects\": [";
	int k = 0;
	while (std::getline (f, line))
	{
		if (!line.empty () && line.back () == '\r')
			line.pop_back ();
		if (line.empty ())
			continue;
		std::vector<std::string> cols;
		std::stringstream ss (line);
		for (std::string c; std::getline (ss, c, '\t');)
			cols.push_back (c);
		if (cols.size () >= 2 && cols[0] == "@gain")
		{
			const float g = float (std::pow (10.0, std::stod (cols[1]) / 20.0));
			for (size_t i = 0; i < audio.frames (); ++i)
				audio.l[i] *= g, audio.r[i] *= g;
			o += std::string (k++ ? ", " : "") + "{\"gain_db\": " + cols[1] + "}";
			continue;
		}
		if (cols.size () < 4)
			return fail ("a chain line is <bundle> <uid> <state|-> <bypass>: " + line);
		if (cols[3] == "1")
		{
			o += std::string (k++ ? ", " : "") + "{\"bypassed\": true}";
			continue;
		}
		Plugin p;
		int32_t latency = 0;
		if (!p.load (cols[0], cols[1], err) || !p.loadState (wide (cols[2]), err) || !p.setup (audio.rate, 512, err) || !p.run (audio, latency, err))
			return fail ("effect " + std::to_string (k + 1) + " (" + (p.name.empty () ? cols[0] : p.name) + "): " + err);
		p.teardown ();
		o += std::string (k++ ? ", " : "") + "{\"name\": " + jstr (p.name) + ", \"latency\": " + std::to_string (latency) + "}";
	}
	if (!writeWav (outWav, audio, err))
		return fail (err);
	std::printf ("%s]}\n", o.c_str ());
	return 0;
}

int editor (const std::string& bundle, const std::string& uid, const std::wstring& in, const std::wstring& out, const std::wstring& title)
{
	Plugin p;
	std::string err;
	if (!p.load (bundle, uid, err) || !p.loadState (in, err))
		return fail (err);
	if (!runEditor (p, title.empty () ? wide (p.name) : title, err) || !p.saveState (out, err))
		return fail (err);
	std::printf ("{\"ok\": true, \"name\": %s}\n", jstr (p.name).c_str ());
	return 0;
}
} // namespace

int wmain (int argc, wchar_t** argv)
{
	HostApplication host;
	PluginContextFactory::instance ().setPluginContext (&host);
	const std::wstring cmd = argc > 1 ? argv[1] : L"";
	auto arg = [&] (int i) { return i < argc ? utf8 (argv[i]) : std::string (); };
	auto warg = [&] (int i) { return i < argc ? std::wstring (argv[i]) : std::wstring (); };
	if (cmd == L"paths")
		return paths ();
	if (cmd == L"scan" && argc >= 3)
		return scan (arg (2));
	if (cmd == L"params" && argc >= 5)
		return params (arg (2), arg (3), warg (4));
	if (cmd == L"state" && argc >= 6)
		return state (arg (2), arg (3), warg (4), warg (5), argc - 6, argv + 6);
	if (cmd == L"render" && argc >= 5)
		return render (warg (2), warg (3), warg (4));
	if (cmd == L"editor" && argc >= 6)
		return editor (arg (2), arg (3), warg (4), warg (5), warg (6));
	return fail ("usage: loom2-vsthost paths | scan <bundle> | params <bundle> <uid> <state|-> | state <bundle> <uid> <state|-> <out> [id=v…] | "
	             "render <chain.tsv> <in.wav> <out.wav> | editor <bundle> <uid> <state|-> <out> [title]");
}
