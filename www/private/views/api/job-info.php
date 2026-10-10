<?php
include('config.php');
require_once('helper.php');

// GET /api/jobs/<id>: state of one scan job.

if (!isset($job_id) || !job_id_is_valid($job_id)) {
        send_json_error(400, 'Invalid job id (expected YYYY-MM-DD-HH-MM-SS)');
}

$record = job_record($job_id);
if ($record === null) {
        send_json_error(404, 'Unknown job');
}

json($record);
?>
