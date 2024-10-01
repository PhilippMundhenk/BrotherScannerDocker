<?php

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

// Check if the scanimage, sleep, and curl processes are running
$result = array(
    'scan' => isProcessRunning('scanimage'),
    'waiting' => isProcessRunning('sleep'),
    'ocr' => isProcessRunning('curl')
);


// Output the result as JSON
header('Content-Type: application/json; charset=utf-8');
echo json_encode($result);

?>
