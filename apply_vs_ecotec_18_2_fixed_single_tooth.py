#!/usr/bin/env python3
'''Keep the VS Ecotec hard 16-tooth wrap and harden the single-tooth cam phase logic.

This is a delta patch for the current VS Ecotec branch.

It requires:
- VS18_2_HARD_COUNT_WRAP already present in trigger_decoder.cpp
- VS18X_PHASE_DEBUG_V2 already present in trigger_central.cpp
'''

from pathlib import Path
import sys

DECODER = Path("firmware/controllers/trigger/trigger_decoder.cpp")
CENTRAL = Path("firmware/controllers/trigger/trigger_central.cpp")

HARD_WRAP_MARKER = "VS18_2_HARD_COUNT_WRAP"
CENTRAL_BASE_MARKER = "VS18X_PHASE_DEBUG_V2"
NEW_MARKER = "VS18X_FIXED_HALF_SINGLE_TOOTH_V3"

OLD_HELPER = '''static angle_t syncVsEcotec18xSingleToothCam(TriggerCentral *tc, int crankDivider) {
\tint nextToothRemainder = (tc->triggerState.currentCycle.current_index + 1) % crankDivider;

\t// If already phased, don't allow the cam to MOVE phase.
\t// But still allow normal same-phase confirmation.
\tif (tc->triggerState.hasSynchronizedPhase()) {
\t\tint currentRemainder = tc->triggerState.getSynchronizationCounter() % crankDivider;

\t\tif (currentRemainder != nextToothRemainder) {
\t\t\t// Wrong cam relationship - ignore it, don't re-phase.
\t\t\treturn 0;
\t\t}
\t}

\treturn tc->syncEnginePhaseAndReport(crankDivider, nextToothRemainder);
}

'''

NEW_HELPER = '''// VS18X_FIXED_HALF_SINGLE_TOOTH_V3
// The 18-2 crank wheel already identifies position within one 360-degree crank revolution.
// The single cam tooth must only choose which of the two crank revolutions is the
// compression revolution. Never derive cam phase from trigger eventIndex.
static angle_t syncVsEcotec18xSingleToothCam(TriggerCentral *tc, operation_mode_e operationMode) {
\tconstexpr int phaseDivider = 2;
\tconstexpr int phaseRemainder = 0;

\tif (operationMode != FOUR_STROKE_CRANK_SENSOR) {
\t\tefiPrintf("VS18X CAM WRONG MODE mode=%d expected=%d",
\t\t\t(int)operationMode,
\t\t\t(int)FOUR_STROKE_CRANK_SENSOR);
\t\treturn 0;
\t}

\tconst int currentHalf = tc->triggerState.getSynchronizationCounter() % phaseDivider;

\t// Once the cam has selected the correct 360-degree half, never let another
\t// cam edge move phase. This also prevents a noisy or late edge from rebuilding
\t// the ignition schedule while the engine is trying to catch.
\tif (tc->triggerState.hasSynchronizedPhase()) {
\t\tif (currentHalf != phaseRemainder) {
\t\t\tefiPrintf("VS18X CAM HALF MISMATCH ignored half=%d expected=%d index=%d cycle=%d",
\t\t\t\tcurrentHalf,
\t\t\t\tphaseRemainder,
\t\t\t\t(int)tc->triggerState.currentCycle.current_index,
\t\t\t\ttc->triggerState.getSynchronizationCounter());
\t\t} else {
\t\t\tefiPrintf("VS18X CAM phase already latched half=%d index=%d cycle=%d",
\t\t\t\tcurrentHalf,
\t\t\t\t(int)tc->triggerState.currentCycle.current_index,
\t\t\t\ttc->triggerState.getSynchronizationCounter());
\t\t}

\t\treturn 0;
\t}

\t// Fixed two-half resolution: result can only be 0 or 360 crank degrees.
\tangle_t phaseShift = tc->syncEnginePhaseAndReport(phaseDivider, phaseRemainder);
\tefiPrintf("VS18X PHASE ACQUIRED fixedHalf=%d shift=%.1f index=%d cycle=%d",
\t\tphaseRemainder,
\t\tphaseShift,
\t\t(int)tc->triggerState.currentCycle.current_index,
\t\ttc->triggerState.getSynchronizationCounter());
\tlogVs18xStateTransition("CAM_SYNC");
\treturn phaseShift;
}

'''

OLD_DEDICATED = '''\t// VS Ecotec 18-2 + single cam, while keeping the existing TT_VS_ECOTEC_18X_1X dropdown name:
\t// the missing-tooth crank pattern gives a hard tooth-zero reference. The cam is only allowed
\t// to resolve the 720-degree phase once. After that, do not let later cam edges move phase.
\tif (engineConfiguration->trigger.type == trigger_type_e::TT_VS_ECOTEC_18X_1X &&
\t\toperationMode == FOUR_STROKE_CRANK_SENSOR &&
\t\tvvtMode == VVT_SINGLE_TOOTH) {
\t\tif (tc->triggerState.hasSynchronizedPhase()) {
\t\t\tefiPrintf("VS18X CAM phase already latched index=%d cycle=%d",
\t\t\t\t(int)tc->triggerState.currentCycle.current_index,
\t\t\t\ttc->triggerState.getSynchronizationCounter());
\t\t\treturn 0;
\t\t}

\t\t// Use the standard 4-stroke crank divider disambiguation. If this ends up 360 degrees out,
\t\t// swap the return remainder between 0 and 1, but do not allow continuous re-phasing.
\t\tangle_t phaseShift = tc->syncEnginePhaseAndReport(crankDivider, 0);
\t\tefiPrintf("VS18X PHASE ACQUIRED shift=%.1f index=%d cycle=%d",
\t\t\tphaseShift,
\t\t\t(int)tc->triggerState.currentCycle.current_index,
\t\t\ttc->triggerState.getSynchronizationCounter());
\t\tlogVs18xStateTransition("CAM_SYNC");
\t\treturn phaseShift;
\t}

'''

NEW_DEDICATED = '''\t// Dedicated VS Ecotec single-tooth phase handling.
\t// The crank decoder supplies the hard 16-tooth 360-degree reference.
\t// The cam only selects one of two engine-cycle halves.
\tif (engineConfiguration->trigger.type == trigger_type_e::TT_VS_ECOTEC_18X_1X &&
\t\tvvtMode == VVT_SINGLE_TOOTH) {
\t\treturn syncVsEcotec18xSingleToothCam(tc, operationMode);
\t}

'''

OLD_GENERIC = '''\tcase VVT_SINGLE_TOOTH:
\t\tif (operationMode == FOUR_STROKE_EIGHTEEN_TIMES_CRANK_SENSOR) {
\t\t\treturn syncVsEcotec18xSingleToothCam(tc, crankDivider);
\t\t}
\t\t[[fallthrough]];
'''

NEW_GENERIC = '''\tcase VVT_SINGLE_TOOTH:
\t\t[[fallthrough]];
'''


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def replace_once(text: str, old: str, new: str, description: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"Could not safely replace {description} (matches={count}).")
    return text.replace(old, new, 1)


def main() -> None:
    if not DECODER.exists() or not CENTRAL.exists():
        fail("Run this from the rusEFI repository root.")

    decoder_text = DECODER.read_text(encoding="utf-8")
    central_text = CENTRAL.read_text(encoding="utf-8")

    if HARD_WRAP_MARKER not in decoder_text:
        fail("Hard 16-tooth wrap is not installed. Apply that patch first.")

    if NEW_MARKER in central_text:
        print("VS Ecotec fixed-half single-tooth cam patch is already installed.")
        return

    if CENTRAL_BASE_MARKER not in central_text:
        fail("Expected VS Ecotec trigger_central.cpp base patch was not found.")

    central_text = replace_once(
        central_text, OLD_HELPER, NEW_HELPER,
        "old event-index-derived single-tooth helper",
    )
    central_text = replace_once(
        central_text, OLD_DEDICATED, NEW_DEDICATED,
        "VS Ecotec dedicated cam phase block",
    )
    central_text = replace_once(
        central_text, OLD_GENERIC, NEW_GENERIC,
        "old eighteen-times single-tooth special case",
    )

    if "nextToothRemainder" in central_text:
        fail("Dynamic event-index cam remainder still exists after patch; refusing to write.")

    CENTRAL.write_text(central_text, encoding="utf-8")

    print("Installed VS Ecotec fixed-half single-tooth cam phase patch.")
    print("Hard 16-tooth crank wrap remains installed and unchanged.")
    print("Cam phase now uses divider=2, fixed remainder=0.")
    print("Cam can only choose 0 or 360 degrees and cannot re-phase once latched.")
    print("Trigger Angle Offset remains unchanged.")


if __name__ == "__main__":
    main()
