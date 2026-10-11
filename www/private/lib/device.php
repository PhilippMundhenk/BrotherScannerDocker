<?php
// Image version and the device capabilities captured at startup, for /api/actions.

function container_version() {
    $v = @file_get_contents('/etc/brotherscanner-version');
    return $v === false ? 'unknown' : trim($v);
}

/**
 * The option lists the device reported at startup (scanimage -A, kept in
 * SCANNER_CAPABILITIES by the entrypoint): mode, resolution (dpi) and
 * source, each with the device default. Empty when the device was not
 * reachable at startup.
 */

function device_capabilities($path = null) {
    $path = $path ?? sys_get_temp_dir() . '/SCANNER_CAPABILITIES';
    $text = @file_get_contents($path);
    $caps = array();
    if ($text === false) {
        return $caps;
    }
    foreach (array('mode', 'resolution', 'source') as $option) {
        if (!preg_match('/^\s*--' . $option . ' (.+?)(?:\s+\[(.*?)\])?\s*$/m', $text, $m)) {
            continue;
        }
        $raw = trim($m[1]);
        $default = isset($m[2]) ? trim($m[2]) : null;
        if ($option === 'resolution') {
            $raw = preg_replace('/dpi$/', '', $raw);
            $default = $default === null ? null : (int)preg_replace('/dpi$/', '', $default);
            if (preg_match('/^(\d+)\.\.(\d+)$/', $raw, $range)) {
                $options = array('min' => (int)$range[1], 'max' => (int)$range[2]);
            } else {
                $options = array_map('intval', array_filter(explode('|', $raw), 'is_numeric'));
            }
        } else {
            $options = array_values(array_filter(array_map('trim', explode('|', $raw)), 'strlen'));
        }
        $caps[$option] = array('options' => $options, 'default' => $default);
    }
    return $caps;
}

/** Thumbnails in the file list are on unless GUI_THUMBNAILS=false. */
