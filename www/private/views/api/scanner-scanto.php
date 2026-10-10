<?php
include('config.php');
require_once('helper.php');

// POST /api/scanner/scanto          form fields: target, [resolution], [mode], [source], [wait]
// GET  /api/scanner/scanto/<target> query:       [resolution], [mode], [source]   (waits for the script)
//
// Starts one of the scan scripts as the scanner user and returns the job id,
// which GET /api/jobs/<id> reports on. Parameters override the container's
// RESOLUTION / SCAN_MODE / SCAN_SOURCE for this job only. The "email" action
// (rear pages) does not create a job: it attaches to the newest job that is
// waiting for rear pages.

function safe_guard_target($target) {
        if (empty($target)) {
                trigger_error("Invalid scan target", E_API);
                send_json_error(400, 'Invalid target');
        }
        if (in_array($target, array('file', 'email', 'image', 'ocr'))) {
                return $target;
        }
        trigger_error("Invalid scan target", E_API);
        send_json_error(400, 'Invalid target');
}

/**
 * Optional per-request scan parameters, validated. Returns the extra command
 * line arguments for the scan script (already shell-escaped).
 */
function scan_parameter_args($params) {
        $args = array();
        if (isset($params['resolution']) && $params['resolution'] !== '') {
                if (!preg_match('/^\d{2,5}$/', $params['resolution'])) {
                        send_json_error(400, 'Invalid resolution (dpi, digits only)');
                }
                $args[] = '--resolution ' . escapeshellarg($params['resolution']);
        }
        foreach (array('mode', 'source') as $name) {
                if (isset($params[$name]) && $params[$name] !== '') {
                        if (!preg_match('/^[A-Za-z0-9 \[\]\(\),&-]{1,60}$/', $params[$name])) {
                                send_json_error(400, "Invalid $name (use the value the device lists at startup)");
                        }
                        $args[] = "--$name " . escapeshellarg($params[$name]);
                }
        }
        return $args;
}

/**
 * A job id that is not yet in use: the timestamp, like scans started on the
 * device get. Waits a second if a job of the same second already exists.
 */
function new_job_id() {
        // Two requests in the same second must not share an id: the scan script
        // only creates its record a moment later, so the id is reserved here with
        // an atomic mkdir (fails for the second caller) in a directory of its own.
        $reservations = sys_get_temp_dir() . '/scanner-job-ids';
        @mkdir($reservations, 0777, true);
        foreach (glob($reservations . '/*') ?: array() as $old) {
                if (time() - @filemtime($old) > 120) {
                        @rmdir($old);
                }
        }
        for ($attempt = 0; $attempt < 3; $attempt++) {
                $id = date('Y-m-d-H-i-s');
                if (job_record($id) === null && !is_dir(sys_get_temp_dir() . '/' . $id) && @mkdir($reservations . '/' . $id)) {
                        return $id;
                }
                sleep(1);
        }
        return date('Y-m-d-H-i-s');
}

/** The newest job waiting for rear pages, or null. */
function waiting_job_id() {
        foreach (job_list(50) as $candidate) {
                if (($candidate['state'] ?? '') === 'waiting_for_rear') {
                        return $candidate['job'];
                }
        }
        return null;
}

function trigger_script($target, $UID, $method, $extra_args, $job_id) {
        $client = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
        $script = '/opt/brother/scanner/brscan-skey/script/scanto' . $target . '.py';
        $command = 'sudo -u \#' . $UID . ' ' . $script;
        if ($job_id !== null) {
                $command .= ' --job-id ' . escapeshellarg($job_id);
        }
        if (!empty($extra_args)) {
                $command .= ' ' . implode(' ', $extra_args);
        }
        // Written to /var/log/scanner.log so a scan can be attributed to the API/web UI;
        // a scan without this line was started by the device (button).
        trigger_error("scan to $target triggered via API ($method) from $client" .
                ($job_id !== null ? " as job $job_id" : '') .
                (empty($extra_args) ? '' : ' with ' . implode(' ', $extra_args)), E_API);

        $response = array(
                'message' => 'Scan triggered',
                'method' => $method == 'return' ? 'post' : 'get',
                'target' => $target,
                'job' => $job_id,
                'status_url' => $job_id !== null ? '/api/jobs/' . $job_id : null,
        );
        if ($method == 'return') {
                popen('sudo -b ' . substr($command, strlen('sudo ')), 'r');
                json($response);
        }
        shell_exec($command);
        $record = $job_id !== null ? job_record($job_id) : null;
        $response['state'] = $record === null ? 'unknown' : $record['state'];
        json($response);
}

$params = $method == 'return' ? $_POST : $_GET;
if (isset($params['wait']) && in_array(strtolower($params['wait']), array('1', 'true', 'yes'))) {
        $method = 'wait';
}
$target = safe_guard_target($scanto);
$extra_args = scan_parameter_args($params);
$job_id = $target === 'email' ? waiting_job_id() : new_job_id();
trigger_script($target, $UID, $method, $extra_args, $job_id);

?>
