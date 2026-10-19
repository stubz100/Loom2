# 08 · Testing CA1 — the motion library (for the author)

Three short checks only you can make. Mixamo files never go into loom2's tests (Adobe's Additional Terms §1), and the click timing is
yours to judge. About 15 minutes in all. Note anything odd in the table at the end.

**Before you start:** run `scripts/dev.ps1` (or the app), open any project, and go to **Animate → Clay**. Make a stage if there is none
(**Shot › New stage…**).

## 1. A Mixamo clip from your local folder (≈ 5 min)

1. Open **☰ › Settings › Motion** and set **Local motion folder** to the folder that holds your Mixamo downloads (for example the repo's
   `mixamo/` folder, or `F:/loom2-motion-mixamo`). Click **Save**.
2. In **Scene › Figures**, add an **Adult**. It is selected.
3. In the **Motion** section, the **Motion library** lists your files under **Local**. Click one, for example *M_Start Walking*.
4. **Check:** the small preview plays the clip on a grey dummy. The line under it reads *N frames at 24 fps · mixamo*.
5. Click **Apply to Figure 1 at the playhead**.
6. **Check:** the timeline gets keys, and pressing **Play** plays the motion on the figure.
7. **Check:** the feet stay planted (*foot lock* is on by default). If the clip should slide (a skid, a roll), untick **foot lock** and
   apply again.

## 2. A walk along a path into a turn and a point, in under 2 minutes of clicks (≈ 5 min)

Time yourself from step 1.

1. Add an **Adult** figure.
2. Click the **Path** tool in the toolbar (the curvy-line icon, or **P**). Click 3–4 points on the floor to make a curve. Switch back to
   **Select** (**W**).
3. In the Motion library: **Starter (CC0)** › open *AnimationLibrary_Godot_Standard* › **Walk_Loop**. Leave **foot lock** and **along
   Figure 1's path** ticked. Click **Apply to Figure 1 at the playhead**.
4. Move the playhead to the end of the walk (the last key). Turn the figure a quarter with the **Rotate** tool (**R**); the turn becomes
   a key.
5. Move the playhead about half a second on. In the poses panel, click **point**.
6. Press **Play**.

**Check:**

- the figure walks the curve without its feet sliding, turns, and ends pointing;
- it took you under 2 minutes.

## 3. The Detailed level (≈ 3 min)

1. Select a figure. In **Motion**, set **level** to **Detailed ♂** (or ♀). After a moment the grey mannequin from the starter set
   replaces the block dummy.
2. Click **fist** on the right hand and **point** on the left.
3. Apply a library clip, or pose it with the joint spheres as before.
4. Open **Performance › From the stage** and click **Render passes**.

**Check:**

- the mannequin follows the poses;
- the hands close and point;
- in the pose pass, a Detailed figure has hands and feet drawn and a Simple figure does not.

## Notes

| Check | OK? | What you saw |
| --- | --- | --- |
| 1 Mixamo | | |
| 2 Walk → turn → point (time) | | |
| 3 Detailed | | |
