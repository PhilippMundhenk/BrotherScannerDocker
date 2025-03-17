<?php
include('config.php');
require_once('helper.php');

function isProcessRunning($processName) {
    // Execute the pgrep command
    $command = "pgrep $processName";
    exec($command, $output, $status);

    // Check if pgrep returned a status of 0, which means the process was found
    if ($status === 0) {
        // Process is running
        return true;
    } else {
        // Process is not running
        return false;
    }
}

function isWaitingStatus() {
    // Check if the waiting status file exists in the temp directory
    $tempDir = sys_get_temp_dir();
    $statusFile = $tempDir . '/STATUS_WAITING';
    
    if (!file_exists($statusFile)) {
        return false;
    }
    
    // Check if file is older than 3 minutes (180 seconds)
    if (time() - filemtime($statusFile) > 180) {
        // File is stale, remove it
        unlink($statusFile);
        return false;
    }
    
    return true;
}

// Check if the scanimage, sleep, and curl processes are running
$result = array(
    'scan' => isProcessRunning('scanimage'),
    'waiting' => isWaitingStatus(),
    'ocr' => isProcessRunning('curl')
);

// Output the result as JSON
json($result);

?>
