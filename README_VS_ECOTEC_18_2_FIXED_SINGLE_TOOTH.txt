VS Ecotec 18-2 hard wrap + fixed single-tooth phase
===================================================

This archive is applied ON TOP OF the hard 16-tooth wrap build.

It does not remove or weaken the crank fix.

Crank behaviour
---------------
- Initial crank synchronization still requires the confirmed real gap.
- Once synchronized, the decoder hard-wraps every 16 physical rising teeth.
- The event sequence remains 0,2,4,...,28,30,0.
- Trigger Angle Offset is unchanged.

Cam behaviour
-------------
- TT_VS_ECOTEC_18X_1X + VVT_SINGLE_TOOTH uses FOUR_STROKE_CRANK_SENSOR logic.
- Phase divider is fixed at 2.
- Phase remainder is fixed at 0.
- The cam can only select 0 degrees or 360 degrees.
- trigger eventIndex is never used to calculate cam phase.
- Once full phase is latched, later cam edges cannot move it.
- A contradictory later cam edge is logged and ignored.

Install from the rusEFI repository root
---------------------------------------

  tar -xzf vs_ecotec_18_2_hard_wrap_fixed_single_tooth_patch.tar.gz
  python3 apply_vs_ecotec_18_2_fixed_single_tooth.py

Then inspect and push:

  git status
  git diff --stat
  git diff -- firmware/controllers/trigger/trigger_central.cpp
  git add firmware/controllers/trigger/trigger_central.cpp
  git commit -m "only:uaefi fix VS Ecotec single tooth phase"
  git push origin HEAD

Expected console messages
-------------------------

Initial cam phase:

  VS18X PHASE ACQUIRED fixedHalf=0 shift=0.0 ...
or
  VS18X PHASE ACQUIRED fixedHalf=0 shift=360.0 ...

Later valid cam edges:

  VS18X CAM phase already latched half=0 ...

A later contradictory edge is not allowed to re-phase:

  VS18X CAM HALF MISMATCH ignored ...
