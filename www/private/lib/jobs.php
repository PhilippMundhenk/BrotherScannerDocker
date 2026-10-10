<?php
// Scan job records written by the scan scripts (see script/jobstate.py) and the OCR queue state.

function jobs_directory() {
    return sys_get_temp_dir() . '/scanner-jobs';
}

function job_id_is_valid($id) {
    return is_string($id) && preg_match('/^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$/', $id) === 1;
}

function ocr_queue_state($job_id) {
    $root = '/scans/.ocr_queue';
    foreach (array('in_progress', 'pending', 'failed') as $dir) {
        foreach (glob($root . '/' . $dir . '/*-' . $job_id . '-*.job') ?: array() as $file) {
            return $dir;
        }
    }
    return null;
}

function job_record($job_id) {
    if (!job_id_is_valid($job_id)) {
        return null;
    }
    $path = jobs_directory() . '/' . $job_id . '.json';
    if (!is_file($path)) {
        return null;
    }
    $record = json_decode((string)@file_get_contents($path), true);
    if (!is_array($record)) {
        return null;
    }
    return job_enrich($record);
}

function job_enrich($record) {
    $id = $record['job'] ?? '';
    $record['url'] = '/api/jobs/' . $id;
    if (!empty($record['file'])) {
        $record['file_url'] = '/api/file/' . rawurlencode($record['file']) . '/download';
        $record['file_exists'] = is_file('/scans/' . $record['file']);
    }
    if (!empty($record['ocr_file'])) {
        $ocr_exists = is_file('/scans/' . $record['ocr_file']);
        $queue = ocr_queue_state($id);
        if ($ocr_exists) {
            $record['ocr'] = 'done';
            $record['ocr_file_url'] = '/api/file/' . rawurlencode($record['ocr_file']) . '/download';
        } elseif ($queue !== null) {
            $record['ocr'] = $queue;
        }
    }
    return $record;
}

function job_list($limit) {
    $files = glob(jobs_directory() . '/*.json') ?: array();
    rsort($files);
    $jobs = array();
    foreach (array_slice($files, 0, $limit) as $path) {
        $record = json_decode((string)@file_get_contents($path), true);
        if (is_array($record)) {
            $jobs[] = job_enrich($record);
        }
    }
    return $jobs;
}

/**
 * Optional API token (API_TOKEN): required for every request that starts a
 * scan or changes files. Accepted as "Authorization: Bearer <token>",
 * "X-API-Token: <token>" or a "token" form/query field. Read-only endpoints
 * and the web UI pages stay open; the UI itself sends the token.
 */
