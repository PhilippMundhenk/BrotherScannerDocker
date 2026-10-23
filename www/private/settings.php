<?php
// Settings: catalogue plus the configuration file (#124).
//
// Three sources, in order of precedence: the container environment (written
// into config.php by the entrypoint and listed in locked.txt), the
// configuration file on the volume, and the catalogue default. The web
// backend overlays the file on every request, so a change on the settings
// page is visible at once wherever the scripts or the UI read it.

function settings_catalogue() {
    static $catalogue = null;
    if ($catalogue === null) {
        $catalogue = include __DIR__ . '/settings-catalogue.php';
    }
    return $catalogue;
}

function settings_catalogue_entry($key) {
    static $index = null;
    if ($index === null) {
        $index = array();
        foreach (settings_catalogue() as $entry) {
            $index[$entry['key']] = $entry;
        }
    }
    return is_string($key) && isset($index[$key]) ? $index[$key] : null;
}

function settings_config_path() {
    global $SCANNER_CONFIG_FILE;
    if (!isset($SCANNER_CONFIG_FILE) && getenv('SCANNER_CONFIG_FILE')) {
        return getenv('SCANNER_CONFIG_FILE');
    }
    if (isset($SCANNER_CONFIG_FILE) && $SCANNER_CONFIG_FILE !== '') {
        return $SCANNER_CONFIG_FILE;
    }
    return '/scans/.config/scanner.conf';
}

function settings_locked_keys() {
    static $locked = null;
    if ($locked === null) {
        $locked = array();
        $lines = @file('/opt/brother/scanner/locked.txt', FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        if (is_array($lines)) {
            foreach ($lines as $line) {
                $locked[trim($line)] = true;
            }
        }
    }
    return $locked;
}

/**
 * The configuration files read during this request, by path. The settings
 * page asks for every one of the ~60 settings and config.php overlays the
 * file once more; reading the file for each of them cost 60 opens per
 * request, which took seconds when /scans is a network share (#196). The
 * cache is dropped whenever this backend writes the file.
 */
function &settings_file_cache() {
    static $cache = array();
    return $cache;
}

function settings_file_cache_clear() {
    $cache = &settings_file_cache();
    $cache = array();
}

/** KEY=VALUE lines of the configuration file (all keys, also unknown ones), read once per request. */
function settings_file_values($path = null) {
    $path = $path ?? settings_config_path();
    $cache = &settings_file_cache();
    if (!array_key_exists($path, $cache)) {
        $cache[$path] = settings_file_read($path);
    }
    return $cache[$path];
}

function settings_file_read($path) {
    $values = array();
    if (!is_file($path)) {
        return $values;  // no configuration file yet: nothing to overlay, nothing to log
    }
    $lines = @file($path, FILE_IGNORE_NEW_LINES);
    if (!is_array($lines)) {
        return $values;
    }
    foreach ($lines as $line) {
        $line = rtrim($line, "\r");
        if (trim($line) === '' || $line[0] === '#' || strpos($line, '=') === false) {
            continue;
        }
        list($key, $value) = explode('=', $line, 2);
        $key = str_replace(' ', '', $key);
        if (!preg_match('/^[A-Z][A-Z0-9_]*$/', $key)) {
            continue;
        }
        if (strlen($value) >= 2 && $value[0] === '"' && substr($value, -1) === '"') {
            $value = substr($value, 1, -1);
        }
        $values[$key] = $value;
    }
    return $values;
}

/** Non-locked file values for catalogue keys, for extract() in config.php. */
function settings_file_overlay() {
    $overlay = array();
    $locked = settings_locked_keys();
    foreach (settings_file_values() as $key => $value) {
        $entry = settings_catalogue_entry($key);
        if (isset($locked[$key]) || $entry === null) {
            continue;
        }
        // the views test booleans with isset($X) && $X: a "false" string would be true
        $overlay[$key] = $entry['type'] === 'bool' ? in_array(strtolower($value), array('true', '1', 'yes', 'on')) : $value;
    }
    return $overlay;
}

function settings_effective_value($key, $file = null) {
    $locked = settings_locked_keys();
    $entry = settings_catalogue_entry($key);
    if (isset($locked[$key]) && isset($GLOBALS[$key])) {
        return array((string)$GLOBALS[$key], 'environment');
    }
    $file = $file ?? settings_file_values();
    if (array_key_exists($key, $file)) {
        return array($file[$key], 'file');
    }
    return array($entry['default'] ?? '', 'default');
}

/** Every catalogue setting with value, source and lock state, secrets masked. */
function settings_all() {
    $result = array();
    $locked = settings_locked_keys();
    $file = settings_file_values();
    foreach (settings_catalogue() as $entry) {
        list($value, $source) = settings_effective_value($entry['key'], $file);
        $item = $entry;
        $item['source'] = $source;
        $item['locked'] = isset($locked[$entry['key']]);
        if ($entry['type'] === 'secret') {
            $item['value'] = '';
            $item['is_set'] = $value !== '';
        } else {
            $item['value'] = $value;
        }
        $result[] = $item;
    }
    return $result;
}

/** Validate one value against the catalogue. Returns array(ok, normalised value or message). */
function settings_validate($key, $value) {
    $entry = settings_catalogue_entry($key);
    if ($entry === null) {
        return array(false, 'unknown setting');
    }
    $value = is_string($value) ? trim($value) : (is_bool($value) ? ($value ? 'true' : 'false') : (string)$value);
    if ($value === '') {
        return array(true, '');  // empty removes the file entry: back to environment or default
    }
    if (strpbrk($value, "\r\n") !== false) {
        return array(false, 'no line breaks allowed');
    }
    switch ($entry['type']) {
        case 'int':
            if (!preg_match('/^-?\d+$/', $value)) {
                return array(false, 'must be a whole number');
            }
            if (isset($entry['min']) && (int)$value < $entry['min']) {
                return array(false, 'must be at least ' . $entry['min']);
            }
            if (isset($entry['max']) && (int)$value > $entry['max']) {
                return array(false, 'must be at most ' . $entry['max']);
            }
            return array(true, (string)(int)$value);
        case 'float':
            if (!is_numeric($value)) {
                return array(false, 'must be a number');
            }
            if (isset($entry['min']) && (float)$value < $entry['min']) {
                return array(false, 'must be at least ' . $entry['min']);
            }
            if (isset($entry['max']) && (float)$value > $entry['max']) {
                return array(false, 'must be at most ' . $entry['max']);
            }
            return array(true, $value);
        case 'bool':
            $lower = strtolower($value);
            if (in_array($lower, array('true', '1', 'yes', 'on'))) {
                return array(true, 'true');
            }
            if (in_array($lower, array('false', '0', 'no', 'off'))) {
                return array(true, 'false');
            }
            return array(false, 'must be true or false');
        default:
            if (strlen($value) > 500) {
                return array(false, 'too long');
            }
            return array(true, $value);
    }
}

/**
 * Apply changes to the configuration file: validated values are written,
 * empty values remove the key, keys set by the environment are refused.
 * Returns array(saved => [...], removed => [...], restart_required => [...], errors => [key => message]).
 */
function settings_save($changes) {
    $locked = settings_locked_keys();
    $errors = array();
    $normalised = array();
    foreach ($changes as $key => $value) {
        if (!is_string($key) || settings_catalogue_entry($key) === null) {
            $errors[$key] = 'unknown setting';
            continue;
        }
        if (isset($locked[$key])) {
            $errors[$key] = 'set by the environment of the container, change it in the compose file';
            continue;
        }
        list($ok, $result) = settings_validate($key, $value);
        if (!$ok) {
            $errors[$key] = $result;
            continue;
        }
        $normalised[$key] = $result;
    }
    if (!empty($errors)) {
        return array('saved' => array(), 'removed' => array(), 'restart_required' => array(), 'errors' => $errors);
    }

    $path = settings_config_path();
    $current = settings_file_values($path);
    $saved = array();
    $removed = array();
    $restart = array();
    foreach ($normalised as $key => $value) {
        $entry = settings_catalogue_entry($key);
        if ($value === '') {
            if (array_key_exists($key, $current)) {
                unset($current[$key]);
                $removed[] = $key;
                if ($entry['restart']) {
                    $restart[] = $key;
                }
            }
            continue;
        }
        if (!array_key_exists($key, $current) || $current[$key] !== $value) {
            $current[$key] = $value;
            $saved[] = $key;
            if ($entry['restart']) {
                $restart[] = $key;
            }
        }
    }

    if (!empty($saved) || !empty($removed)) {
        $error = settings_write_file($path, $current);
        if ($error !== null) {
            return array('saved' => array(), 'removed' => array(), 'restart_required' => array(),
                         'errors' => array('_file' => $error));
        }
        trigger_error("settings saved to $path: " . implode(', ', array_merge($saved, array_map(function ($k) { return "-$k"; }, $removed))), E_API);
    }
    return array('saved' => $saved, 'removed' => $removed, 'restart_required' => array_values(array_unique($restart)), 'errors' => array());
}

/** Write KEY=VALUE lines atomically. Returns null, or the reason it could not. */
function settings_write_file($path, $values) {
    $dir = dirname($path);
    if (!is_dir($dir) && !@mkdir($dir, 0777, true)) {
        return "cannot create $dir";
    }
    $lines = array("# BrotherScannerDocker configuration, written by the settings page on " . date('Y-m-d H:i:s'),
                   "# Environment variables of the container take precedence over this file.");
    ksort($values);
    foreach ($values as $key => $value) {
        $lines[] = $key . '=' . $value;
    }
    $tmp = $path . '.' . getmypid() . '.tmp';
    if (@file_put_contents($tmp, implode("\n", $lines) . "\n") === false || !@rename($tmp, $path)) {
        @unlink($tmp);
        return "cannot write $path";
    }
    @chmod($path, 0664);
    clearstatcache(true, $path);
    settings_file_cache_clear();  // the next read in this request sees what was just written
    return null;
}

/**
 * Migration: copy every setting the environment sets into the configuration
 * file with its current value, secrets included (#161). The environment keeps
 * winning until its entries are removed from the compose file and the
 * container restarted; then the file carries on with the same values.
 * Returns array(written => [...], unchanged => [...], environment => [...], error => string|null).
 */
function settings_import_environment() {
    $locked = settings_locked_keys();
    $path = settings_config_path();
    $current = settings_file_values($path);
    $written = array();
    $unchanged = array();
    foreach (settings_catalogue() as $entry) {
        $key = $entry['key'];
        if (!isset($locked[$key]) || !isset($GLOBALS[$key])) {
            continue;
        }
        $value = $GLOBALS[$key];
        $value = is_bool($value) ? ($value ? 'true' : 'false') : (string)$value;
        if (array_key_exists($key, $current) && $current[$key] === $value) {
            $unchanged[] = $key;
            continue;
        }
        $current[$key] = $value;
        $written[] = $key;
    }
    $error = null;
    if (!empty($written)) {
        $error = settings_write_file($path, $current);
        if ($error === null) {
            trigger_error("environment values copied to $path: " . implode(', ', $written), E_API);
        }
    }
    return array('written' => $error === null ? $written : array(), 'unchanged' => $unchanged,
                 'environment' => array_merge($written, $unchanged), 'error' => $error);
}

function settings_enabled() {
    global $ALLOW_GUI_SETTINGS;
    return isset($ALLOW_GUI_SETTINGS) && in_array(strtolower((string)$ALLOW_GUI_SETTINGS), array('true', '1', 'yes', 'on'));
}
?>
