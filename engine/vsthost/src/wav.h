// D127 (AU3): the WAV files loom2 hands the host and gets back — read as stereo 32-bit float (mono doubled, more channels: the first two),
// written as stereo 32-bit float at the same rate.
#pragma once
#include <string>
#include <vector>

struct Stereo
{
	double rate = 48000.0;
	std::vector<float> l, r;
	size_t frames () const { return l.size (); }
};

bool readWav (const std::wstring& path, Stereo& out, std::string& err);
bool writeWav (const std::wstring& path, const Stereo& in, std::string& err);
