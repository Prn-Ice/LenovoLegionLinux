// SPDX-License-Identifier: GPL-2.0-or-later
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef uint32_t u32;
#include "../kernel_module/power-defaults.h"

int main(void)
{
	struct capdata01 rows[] = {
		{ 0x0102ff00, 1, 0, 1, 0, 100 },
		{ 0x01020200, 0, 55, 1, 0, 100 },
		{ 0x01020101, 1, 30, 1, 0, 100 },
	};
	u32 value = 999;

	assert(capdata_default_lookup(rows, 3, true, 0x01020000, 255,
				      &value) == CAPDATA_VALID && value == 0);
	assert(capdata_default_lookup(rows, 3, true, 0x01020000, 2,
				      &value) == CAPDATA_UNSUPPORTED);
	assert(capdata_default_lookup(rows, 3, true, 0x01020000, 1,
				      &value) == CAPDATA_MISSING);
	assert(capdata_default_lookup(rows, 3, false, 0x01020000, 255,
				      &value) == CAPDATA_INVALID);
	rows[2] = rows[0];
	assert(capdata_default_lookup(rows, 3, true, 0x01020000, 255,
				      &value) == CAPDATA_INVALID);
	rows[2].id = 0;
	rows[0].default_value = 101;
	assert(capdata_default_lookup(rows, 3, true, 0x01020000, 255,
				      &value) == CAPDATA_INVALID);
	rows[0].min_value = 102;
	assert(capdata_default_lookup(rows, 3, true, 0x01020000, 255,
				      &value) == CAPDATA_INVALID);
	return 0;
}
