# Firmware power-default diagnostics, version 1

The read-only `power_defaults_v1` platform-device sysfs attribute reports the
driver's existing probe-time cache of `LENOVO_CAPABILITY_DATA_01`, GUID
`7A8F5407-CB67-4D6E-B547-39B3BE018154`. Reading the attribute does not call
GetFeatureValue, query firmware again, change mode or write a limit. Probe already
queries the firmware capability block; this is not a promise that the firmware's
implementation of that original query has no side effects.

Each line is `feature_hex mode_decimal status value`, with `-` instead of a
value unless status is `valid`. Features use the existing Other Method IDs;
the capability ID adds the mode in bits 15..8 and uses sub-ID zero. Modes 1,
2, 3, 224 and 255 mean low-power, balanced, performance, max-power and custom,
respectively. These are capability defaults *for that mode*, not evidence that
firmware applies those values in that mode. Values are watts except 01040000
and 02030000 (degrees Celsius); the unit of 01070000 (L1 tau) has not been
verified here and must not be assumed. Features 0101..0107
are CPU short, long, peak, temperature, APU PPT, cross-load, and L1 tau;
0201..0204 are GPU boost/PPAB, cTGP, temperature and AC target offset.

`missing` means no matching row in a completely read cache; `unsupported` means
a matching row has its support bit clear; `valid` means a supported unique row
whose explicit default is in its reported range, including zero; `invalid`
means the cache was unavailable/incomplete, the key duplicated, or its range
or default invalid. A failed query, truncated record, absent GUID or overflow
of the 80-row cache makes all results invalid. Neither a missing row nor a
valid row establishes whether an existing control is exposed or writable.
Device model and BIOS identity must be read separately from DMI and matched by
the consumer; this interface does not authenticate firmware or certify a preset.

This is a diagnostic contract, not permission to restore. Complete exact-model
coverage and writable-field validation remain required. In particular, no raw
82Y4/M1CN48WW capability records or original DSDT are retained here; the
historical PPAB 20 W initializer versus observed 0 W is unresolved. Neither
number is approved for restoration. Existing zero-based visibility is unchanged.
No hardware validation has been performed for this export.
