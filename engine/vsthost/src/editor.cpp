// D127 (AU3): a plug-in's own editor in a window of the host's — the author sets it up by mouse; what the editor changes reaches the
// processor (a silent block carries the edits) before loom2 saves the state. A plug-in without an editor of its own says so.
#include "host.h"

#include "pluginterfaces/gui/iplugview.h"

#include <windows.h>

#include <algorithm>

using namespace Steinberg;
using namespace Steinberg::Vst;

namespace {
const DWORD STYLE = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_CLIPCHILDREN;

/** The host's side of the editor: the frame it lives in and the handler its edits arrive through. Owned by the window's lifetime. */
class EditorHost : public IPlugFrame, public IComponentHandler
{
public:
	HWND hwnd = nullptr;
	IPtr<IPlugView> view;
	std::map<ParamID, ParamValue> edits;
	bool resizable = false;

	tresult PLUGIN_API queryInterface (const TUID iid, void** obj) override
	{
		if (FUnknownPrivate::iidEqual (iid, IPlugFrame::iid) || FUnknownPrivate::iidEqual (iid, FUnknown::iid))
		{
			*obj = static_cast<IPlugFrame*> (this);
			return kResultOk;
		}
		if (FUnknownPrivate::iidEqual (iid, IComponentHandler::iid))
		{
			*obj = static_cast<IComponentHandler*> (this);
			return kResultOk;
		}
		*obj = nullptr;
		return kNoInterface;
	}
	uint32 PLUGIN_API addRef () override { return 1; }
	uint32 PLUGIN_API release () override { return 1; }

	tresult PLUGIN_API resizeView (IPlugView* v, ViewRect* r) override
	{
		if (!hwnd || !r)
			return kInvalidArgument;
		RECT rc {0, 0, r->getWidth (), r->getHeight ()};
		AdjustWindowRectEx (&rc, STYLE | (resizable ? WS_THICKFRAME | WS_MAXIMIZEBOX : 0), FALSE, 0);
		SetWindowPos (hwnd, nullptr, 0, 0, rc.right - rc.left, rc.bottom - rc.top, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
		v->onSize (r);
		return kResultTrue;
	}

	tresult PLUGIN_API beginEdit (ParamID) override { return kResultOk; }
	tresult PLUGIN_API performEdit (ParamID id, ParamValue v) override
	{
		edits[id] = v;
		return kResultOk;
	}
	tresult PLUGIN_API endEdit (ParamID) override { return kResultOk; }
	tresult PLUGIN_API restartComponent (int32) override { return kResultOk; }
};

LRESULT CALLBACK windowProc (HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
	auto* host = reinterpret_cast<EditorHost*> (GetWindowLongPtrW (hwnd, GWLP_USERDATA));
	switch (msg)
	{
		case WM_SIZE:
			if (host && host->view && host->resizable)
			{
				ViewRect r {0, 0, LOWORD (lp), HIWORD (lp)};
				host->view->onSize (&r);
			}
			return 0;
		case WM_CLOSE:
			DestroyWindow (hwnd);
			return 0;
		case WM_DESTROY:
			PostQuitMessage (0);
			return 0;
	}
	return DefWindowProcW (hwnd, msg, wp, lp);
}
} // namespace

bool runEditor (Plugin& p, const std::wstring& title, std::string& err)
{
	if (!p.controller)
	{
		err = "the plug-in has no controller, so no editor";
		return false;
	}
	EditorHost host;
	p.controller->setComponentHandler (&host);
	host.view = owned (p.controller->createView (ViewType::kEditor));
	if (!host.view || host.view->isPlatformTypeSupported (kPlatformTypeHWND) != kResultTrue)
	{
		p.controller->setComponentHandler (nullptr);
		err = "the plug-in has no editor of its own";
		return false;
	}
	host.resizable = host.view->canResize () == kResultTrue;
	ViewRect size {0, 0, 480, 320};
	host.view->getSize (&size);

	OleInitialize (nullptr);
	WNDCLASSEXW wc {sizeof (wc)};
	wc.lpfnWndProc = windowProc;
	wc.hInstance = GetModuleHandleW (nullptr);
	wc.hCursor = LoadCursorW (nullptr, IDC_ARROW);
	wc.hbrBackground = reinterpret_cast<HBRUSH> (COLOR_WINDOW + 1);
	wc.lpszClassName = L"loom2-vsthost-editor";
	RegisterClassExW (&wc);
	const DWORD style = STYLE | (host.resizable ? WS_THICKFRAME | WS_MAXIMIZEBOX : 0);
	RECT rc {0, 0, size.getWidth (), size.getHeight ()};
	AdjustWindowRectEx (&rc, style, FALSE, 0);
	// centred on the monitor under the mouse — where the author just clicked in loom2
	POINT at {};
	GetCursorPos (&at);
	MONITORINFO mi {sizeof (mi)};
	GetMonitorInfoW (MonitorFromPoint (at, MONITOR_DEFAULTTOPRIMARY), &mi);
	const int w = rc.right - rc.left, h = rc.bottom - rc.top;
	const int x = mi.rcWork.left + std::max (0L, (mi.rcWork.right - mi.rcWork.left - w) / 2);
	const int y = mi.rcWork.top + std::max (0L, (mi.rcWork.bottom - mi.rcWork.top - h) / 2);
	host.hwnd = CreateWindowExW (0, wc.lpszClassName, title.c_str (), style, x, y, w, h, nullptr, nullptr, wc.hInstance, nullptr);
	if (!host.hwnd)
	{
		err = "the editor's window was not made";
		return false;
	}
	SetWindowLongPtrW (host.hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR> (&host));
	host.view->setFrame (&host);
	if (host.view->attached (host.hwnd, kPlatformTypeHWND) != kResultOk)
	{
		DestroyWindow (host.hwnd);
		err = "the plug-in's editor did not open";
		return false;
	}
	ShowWindow (host.hwnd, SW_SHOWNORMAL);
	SetWindowPos (host.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE);    // in front of loom2 once, then an ordinary window
	SetWindowPos (host.hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE);
	SetForegroundWindow (host.hwnd);
	MSG msg;
	while (GetMessageW (&msg, nullptr, 0, 0) > 0)
	{
		TranslateMessage (&msg);
		DispatchMessageW (&msg);
	}
	host.view->removed ();
	host.view->setFrame (nullptr);
	host.view = nullptr;
	p.controller->setComponentHandler (nullptr);
	// the edits reach the processor in one silent block, so the component's state carries them
	if (!host.edits.empty ())
	{
		if (!p.setup (48000.0, 64, err))
			return false;
		for (auto& [id, v] : host.edits)
			p.queueParam (id, v);
		Stereo silence;
		silence.l.assign (64, 0.f);
		silence.r.assign (64, 0.f);
		int32_t latency = 0;
		if (!p.run (silence, latency, err))
			return false;
		p.teardown ();
	}
	OleUninitialize ();
	return true;
}
