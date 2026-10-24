// D127 (AU3): a small RIFF/WAVE reader and writer — PCM 16 / 24 / 32-bit integer and 32 / 64-bit float, plain or WAVE_FORMAT_EXTENSIBLE.
#include "wav.h"

#include <cstdint>
#include <cstring>
#include <fstream>

namespace {
uint16_t u16 (const unsigned char* p) { return uint16_t (p[0] | (p[1] << 8)); }
uint32_t u32 (const unsigned char* p) { return uint32_t (p[0] | (p[1] << 8) | (p[2] << 16) | (uint32_t (p[3]) << 24)); }
}

bool readWav (const std::wstring& path, Stereo& out, std::string& err)
{
	std::ifstream f (path, std::ios::binary);
	if (!f)
	{
		err = "cannot open the input WAV";
		return false;
	}
	std::vector<unsigned char> d ((std::istreambuf_iterator<char> (f)), std::istreambuf_iterator<char> ());
	if (d.size () < 12 || std::memcmp (d.data (), "RIFF", 4) != 0 || std::memcmp (d.data () + 8, "WAVE", 4) != 0)
	{
		err = "the input is not a RIFF/WAVE file";
		return false;
	}
	uint16_t fmt = 0, channels = 0, bits = 0;
	uint32_t rate = 0;
	const unsigned char* data = nullptr;
	size_t dataSize = 0;
	for (size_t pos = 12; pos + 8 <= d.size ();)
	{
		uint32_t size = u32 (&d[pos + 4]);
		const unsigned char* body = &d[pos + 8];
		size_t avail = std::min<size_t> (size, d.size () - pos - 8);
		if (std::memcmp (&d[pos], "fmt ", 4) == 0 && avail >= 16)
		{
			fmt = u16 (body);
			channels = u16 (body + 2);
			rate = u32 (body + 4);
			bits = u16 (body + 14);
			if (fmt == 0xFFFE && avail >= 26)
				fmt = u16 (body + 24); // the sub-format's first two bytes: 1 PCM, 3 float
		}
		else if (std::memcmp (&d[pos], "data", 4) == 0)
		{
			data = body;
			dataSize = avail;
		}
		pos += 8 + size + (size & 1);
	}
	if (!data || !channels || !rate || (fmt != 1 && fmt != 3))
	{
		err = "the input WAV has no PCM or float data";
		return false;
	}
	const size_t bytes = bits / 8, frame = bytes * channels;
	if (!bytes || (fmt == 1 && bits != 16 && bits != 24 && bits != 32) || (fmt == 3 && bits != 32 && bits != 64))
	{
		err = "the input WAV's sample format is not supported (" + std::to_string (bits) + " bits)";
		return false;
	}
	const size_t n = dataSize / frame;
	out.rate = rate;
	out.l.resize (n);
	out.r.resize (n);
	auto sample = [&] (const unsigned char* p) -> float {
		if (fmt == 3)
		{
			if (bits == 32)
			{
				float v;
				std::memcpy (&v, p, 4);
				return v;
			}
			double v;
			std::memcpy (&v, p, 8);
			return float (v);
		}
		if (bits == 16)
			return int16_t (u16 (p)) / 32768.0f;
		if (bits == 24)
			return float (int32_t (uint32_t (p[0] << 8) | uint32_t (p[1] << 16) | (uint32_t (p[2]) << 24)) / 2147483648.0);
		return float (int32_t (u32 (p)) / 2147483648.0);
	};
	for (size_t i = 0; i < n; ++i)
	{
		const unsigned char* p = data + i * frame;
		out.l[i] = sample (p);
		out.r[i] = channels > 1 ? sample (p + bytes) : out.l[i];
	}
	return true;
}

bool writeWav (const std::wstring& path, const Stereo& in, std::string& err)
{
	std::ofstream f (path, std::ios::binary);
	if (!f)
	{
		err = "cannot write the output WAV";
		return false;
	}
	const uint32_t n = uint32_t (in.frames ()), dataSize = n * 8, rate = uint32_t (in.rate + 0.5);
	auto put16 = [&] (uint16_t v) { f.put (char (v & 0xFF)).put (char (v >> 8)); };
	auto put32 = [&] (uint32_t v) { put16 (uint16_t (v & 0xFFFF)); put16 (uint16_t (v >> 16)); };
	f.write ("RIFF", 4);
	put32 (36 + dataSize);
	f.write ("WAVEfmt ", 8);
	put32 (16);
	put16 (3);           // IEEE float
	put16 (2);
	put32 (rate);
	put32 (rate * 8);
	put16 (8);
	put16 (32);
	f.write ("data", 4);
	put32 (dataSize);
	for (uint32_t i = 0; i < n; ++i)
	{
		f.write (reinterpret_cast<const char*> (&in.l[i]), 4);
		f.write (reinterpret_cast<const char*> (&in.r[i]), 4);
	}
	if (!f)
	{
		err = "the output WAV was not written whole";
		return false;
	}
	return true;
}
