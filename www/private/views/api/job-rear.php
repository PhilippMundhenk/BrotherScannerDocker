<?php
include('config.php');
require_once('helper.php');

// POST /api/jobs/<id>/rear: scan the rear pages for a specific job that is
// waiting for them (the "Scan to E-mail" action addresses the latest job).

if (!isset($job_id) || !job_id_is_valid($job_id)) {
        send_json_error(400, 'Invalid job id (expected YYYY-MM-DD-HH-MM-SS)');
}

$record = job_record($job_id);
if ($record === null) {
        send_json_error(404, 'Unknown job');
}
if (($record['state'] ?? '') !== 'waiting_for_rear') {
        send_json_error(409, 'Job is not waiting for rear pages (state: ' . ($record['state'] ?? 'unknown') . ')');
}

$client = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
trigger_error("rear scan for job $job_id triggered via API from $client", E_API);
$command = 'sudo -b -u \#' . $UID . ' /opt/brother/scanner/brscan-skey/script/scantoemail.py --job-id ' . escapeshellarg($job_id);
popen($command, 'r');

json(array(
        'message' => 'Rear scan triggered',
        'job' => $job_id,
        'status_url' => '/api/jobs/' . $job_id,
));
?>
