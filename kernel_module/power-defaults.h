/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef LEGION_POWER_DEFAULTS_H
#define LEGION_POWER_DEFAULTS_H

struct capdata01 {
	u32 id;
	u32 supported;
	u32 default_value;
	u32 step;
	u32 min_value;
	u32 max_value;
};

enum capdata_default_status {
	CAPDATA_MISSING,
	CAPDATA_UNSUPPORTED,
	CAPDATA_VALID,
	CAPDATA_INVALID,
};

/* A bad cache or duplicate key makes even an apparently valid row ambiguous. */
static enum capdata_default_status
capdata_default_lookup(const struct capdata01 *rows, int count, bool complete,
		       u32 feature, u32 mode, u32 *value)
{
	const struct capdata01 *found = NULL;
	u32 id = feature | (mode << 8);
	int i;

	if (!complete)
		return CAPDATA_INVALID;
	for (i = 0; i < count; i++) {
		if (rows[i].id != id)
			continue;
		if (found)
			return CAPDATA_INVALID;
		found = &rows[i];
	}
	if (!found)
		return CAPDATA_MISSING;
	if (!(found->supported & 1))
		return CAPDATA_UNSUPPORTED;
	if (found->min_value > found->max_value ||
	    found->default_value < found->min_value ||
	    found->default_value > found->max_value)
		return CAPDATA_INVALID;
	*value = found->default_value;
	return CAPDATA_VALID;
}

#endif
