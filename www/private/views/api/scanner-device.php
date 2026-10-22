<?php
include('config.php');
require_once('helper.php');

// GET /api/scanner/device: the scanner's own state, read from the device over
// SNMP by `openskey status` (openskey ships in the image, see doc/setup.md):
// whether the device currently lists this container as a Scan-to-PC
// destination (registered), model, serial, firmware, the first line of the
// panel display, and the device's network-scan / scan-key capability flags.
// Scanner objects only; this is a scanner, not a printer monitor.
//
// Answers are cached for DEVICE_STATUS_CACHE_SECONDS (default 10) so a client
// that polls every few seconds (Home Assistant) does not query the device on
// every request. DEVICE_STATUS=false turns the endpoint off (404).

function device_status_enabled() {
    global $DEVICE_STATUS;
    if (!isset($DEVICE_STATUS)) {
        return true;
    }
    if (is_bool($DEVICE_STATUS)) {
        return $DEVICE_STATUS;  // config.php and the settings overlay hand booleans over
    }
    return !in_array(strtolower((string)$DEVICE_STATUS), array('false', '0', 'no', 'off'));
}

function device_status_cache_seconds() {
    global $DEVICE_STATUS_CACHE_SECONDS;
    if (!isset($DEVICE_STATUS_CACHE_SECONDS) || !is_numeric($DEVICE_STATUS_CACHE_SECONDS)) {
        return 10;
    }
    return max(0, (int)$DEVICE_STATUS_CACHE_SECONDS);
}

/** Runs `openskey status` against the device; the decoded JSON, or null when it gave none. */
function device_status_query($ip, $port) {
    $command = 'IPADDRESS=' . escapeshellarg($ip) . ' SKEY_DEVICE_PORT=' . escapeshellarg((string)$port)
        . ' timeout 20 /usr/local/bin/openskey status 2>/dev/null';
    $output = shell_exec($command);
    $status = json_decode((string)$output, true);
    return is_array($status) ? $status : null;
}

if (!device_status_enabled()) {
    send_json_error(404, 'Device status is disabled (DEVICE_STATUS=false)');
}
$ip = isset($IPADDRESS) && $IPADDRESS !== '' ? (string)$IPADDRESS : '';
if ($ip === '') {
    send_json_error(500, 'IPADDRESS is not configured');
}
$port = isset($SKEY_DEVICE_PORT) && is_numeric($SKEY_DEVICE_PORT) ? (int)$SKEY_DEVICE_PORT : 161;

$cache = sys_get_temp_dir() . '/DEVICE_STATUS.json';
$ttl = device_status_cache_seconds();
$status = null;
if ($ttl > 0 && is_file($cache) && time() - filemtime($cache) < $ttl) {
    $status = json_decode((string)@file_get_contents($cache), true);
    if (is_array($status)) {
        $status['cached'] = true;
    }
}
if (!is_array($status)) {
    $status = device_status_query($ip, $port);
    if ($status === null) {
        send_json_error(500, 'openskey status gave no answer');
    }
    $status['checked'] = date('c');
    @file_put_contents($cache, json_encode($status));
    @chmod($cache, 0644);
    $status['cached'] = false;
}

json($status);
?>
