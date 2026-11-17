#!/bin/bash
set -eu

DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
TMP=$(mktemp -d)
trap 'rm -f "$TMP/harness.c" "$TMP/harness"; rmdir "$TMP"' EXIT

# Test the driver's actual store handler with firmware calls replaced by stubs.
cat >"$TMP/harness.c" <<'C'
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stddef.h>
#include <sys/types.h>

#define LEGION_WMI_POWERMODE_CUSTOM 255
#define pr_info(...) ((void)0)
#define mutex_lock(lock) ((void)(lock))
#define mutex_unlock(lock) ((void)(lock))

enum OtherMethodFeature { TEST_FEATURE };
struct model_config { bool power_writes_custom_only; };
struct legion_private { const struct model_config *conf; int fancurve_mutex; };
static int mode, read_error, clamp_error, set_error, read_calls, set_calls;

static int clamped_value(struct legion_private *priv,
			enum OtherMethodFeature feature, const char *buf, int *value)
{
	(void)priv; (void)feature; (void)buf;
	*value = 54;
	return clamp_error;
}

static int read_powermode(struct legion_private *priv, int *value)
{
	(void)priv;
	read_calls++;
	if (!read_error)
		*value = mode;
	return read_error;
}

static int wmi_other_method_set_value(enum OtherMethodFeature feature,
				    int value, int *output)
{
	(void)feature;
	assert(value == 54);
	*output = 0;
	set_calls++;
	return set_error;
}
C

sed -n '/^static ssize_t wmi_common_method_other_store(/,/^}/p' \
  "$DIR/../kernel_module/legion-laptop.c" >>"$TMP/harness.c"

cat >>"$TMP/harness.c" <<'C'
int main(void)
{
	struct model_config guarded = { .power_writes_custom_only = true };
	struct model_config ordinary = { .power_writes_custom_only = false };
	struct legion_private priv = { .conf = &guarded };

	/* Balanced mode must not write a setting that firmware would ignore. */
	mode = 1;
	assert(wmi_common_method_other_store(&priv, "54", 2, TEST_FEATURE) == -EPERM);
	assert(set_calls == 0);

	/* A failed mode read must also leave firmware untouched. */
	read_error = -EIO;
	assert(wmi_common_method_other_store(&priv, "54", 2, TEST_FEATURE) == -EPERM);
	assert(set_calls == 0);

	read_error = 0;
	mode = LEGION_WMI_POWERMODE_CUSTOM;
	assert(wmi_common_method_other_store(&priv, "54", 2, TEST_FEATURE) == 2);
	assert(set_calls == 1);

	/* Preserve upstream input validation and setter-error handling. */
	clamp_error = -ERANGE;
	assert(wmi_common_method_other_store(&priv, "54", 2, TEST_FEATURE) == -ERANGE);
	assert(set_calls == 1);
	clamp_error = 0;
	set_error = -EIO;
	assert(wmi_common_method_other_store(&priv, "54", 2, TEST_FEATURE) == -EINVAL);
	assert(set_calls == 2);

	/* Models without the M1CN guard keep their existing behavior. */
	priv.conf = &ordinary;
	read_error = -EIO;
	set_error = 0;
	read_calls = 0;
	assert(wmi_common_method_other_store(&priv, "54", 2, TEST_FEATURE) == 2);
	assert(read_calls == 0 && set_calls == 3);
	return 0;
}
C

gcc -std=gnu11 -Wall -Wextra -Werror "$TMP/harness.c" -o "$TMP/harness"
"$TMP/harness"
