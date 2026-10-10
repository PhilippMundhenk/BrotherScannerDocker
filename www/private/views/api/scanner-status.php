<?php
include('config.php');
require_once('helper.php');

function isProcessRunning($processName) {
    // Execute the pgrep command
    $command = "pgrep $processName";
    exec($command, $output, $status);

    // Check if pgrep returned a status of 0, which means the process was found
    return $status === 0;
}

/**
 * Checks a status file written by scanner.py (STATUS_<NAME> in the temp
 * directory). A file older than $maxAgeSeconds is considered stale (the
 * writing process died) and is removed.
 */
function isStatusSet($name, $maxAgeSeconds) {
    $statusFile = sys_get_temp_dir() . '/STATUS_' . strtoupper($name);

    if (!file_exists($statusFile)) {
        return false;
    }

    if (time() - filemtime($statusFile) > $maxAgeSeconds) {
        @unlink($statusFile);
        return false;
    }

    return true;
}

/**
 * Scanner reachability as checked by the entrypoint every SCANNER_PING_INTERVAL
 * seconds (STATUS_REACHABLE holds 1 or 0). null when the check is disabled or
 * has not run for a while.
 */
function scannerReachable() {
    $file = sys_get_temp_dir() . '/STATUS_REACHABLE';
    if (!file_exists($file) || time() - filemtime($file) > 600) {
        return null;
    }
    return trim((string)@file_get_contents($file)) === '1';
}

// scan:      scanner.py marks the scan phase with a status file; the process
//            check stays as a fallback for scans started outside the scripts.
// waiting:   the front scan is waiting for rear pages (status file, 3 minutes).
// ocr:       the OCR queue worker is uploading (curl).
// reachable: the device answered the entrypoint's connection check.
$result = array(
    'scan' => isStatusSet('scan', 600) || isProcessRunning('scanimage'),
    'waiting' => isStatusSet('waiting', 180),
    'ocr' => isProcessRunning('curl'),
    'reachable' => scannerReachable(),
);

// Output the result as JSON
json($result);

?>
