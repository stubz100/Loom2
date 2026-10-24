// D127 (AU3): one VST3 effect as loom2's host holds it — loaded from its bundle by class id, its state from and to a file, set up for
// offline stereo processing, run over a whole signal (its latency taken off), its parameters listed and set.
#pragma once

#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/parameterchanges.h"
#include "public.sdk/source/vst/hosting/plugprovider.h"
#include "public.sdk/source/vst/hosting/processdata.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include "pluginterfaces/vst/ivstprocesscontext.h"

#include <map>
#include <string>
#include <vector>

#include "wav.h"

struct Plugin
{
	VST3::Hosting::Module::Ptr module;
	Steinberg::IPtr<Steinberg::Vst::PlugProvider> provider;
	Steinberg::IPtr<Steinberg::Vst::IComponent> component;
	Steinberg::IPtr<Steinberg::Vst::IEditController> controller;
	Steinberg::IPtr<Steinberg::Vst::IAudioProcessor> processor;
	std::string name, vendor;
	int32_t inChannels = 2, outChannels = 2;
	int32_t block = 512;
	double rate = 48000.0;
	bool active = false;

	~Plugin ();
	/** The effect class `uid` (empty: the bundle's first effect) of the bundle at `path`. */
	bool load (const std::string& path, const std::string& uid, std::string& err);
	/** loom2's state file (`-` or empty: the plug-in's defaults): the component's state, then the controller's. */
	bool loadState (const std::wstring& file, std::string& err);
	bool saveState (const std::wstring& file, std::string& err);
	/** Offline, 32-bit float, the main buses stereo (or what the plug-in takes), any side-chain off. */
	bool setup (double sampleRate, int32_t maxBlock, std::string& err);
	void teardown ();
	/** Parameter changes handed to the next process call (normalised values), and to the controller. */
	void queueParam (Steinberg::Vst::ParamID id, Steinberg::Vst::ParamValue v);
	/** The whole signal through the plug-in, in blocks; its reported latency is taken off so the output lines up with the input. */
	bool run (Stereo& audio, int32_t& latency, std::string& err);

private:
	Steinberg::Vst::HostProcessData data;
	Steinberg::Vst::ParameterChanges changes {64};
	Steinberg::Vst::ProcessContext context {};
	std::map<Steinberg::Vst::ParamID, Steinberg::Vst::ParamValue> pending;
	int64_t position = 0;
	bool processBlock (const float* l, const float* r, float* ol, float* or_, int32_t n);
};

std::string utf8 (const std::wstring& w);
std::wstring wide (const std::string& s);
std::string jstr (const std::string& s);
