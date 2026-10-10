<?php
include('config.php');
require_once('helper.php');

// GET /api/jobs[?limit=N]: recent scan jobs, newest first, with their state
// (from the records the scan scripts write) and the OCR queue position.

$limit = 50;
if (isset($_GET['limit']) && is_numeric($_GET['limit'])) {
        $limit = max(1, min(500, (int)$_GET['limit']));
}

json(job_list($limit));
?>
