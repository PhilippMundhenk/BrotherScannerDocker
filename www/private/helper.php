<?php

function json($data){

    header('Content-Type: application/json');
    print_r(json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    die();

}


function send_json_error($http_code, $message){

    header('Content-Type: application/json');
    http_response_code($http_code);
    json(array('code' => $http_code, 'message' => $message));  // json() exits
}


function send_error_page($http_code, $page_title='', $page_message=''){
    http_response_code($http_code);
    if ($page_title != '' && $page_message != ''){
        require 'views/frontend/error.php';
    }
    die();
}

/**
 * Constructs a safe file path within a specified directory.
 *
 * This function takes a directory and a filename, constructs the full file path,
 * and ensures that the file path is within the specified directory. It prevents
 * directory traversal attacks by validating the real path of the constructed file path.
 *
 * @param string $directory The directory in which the file should be located.
 * @param string $filename The name of the file.
 * @return string|false The real path to the file if it is within the specified directory, or false if it is not.
 */
function file_get_real_filepath($directory, $filename) {

    $filename = basename($filename);
    if ($filename === '' || $filename === '.' || $filename === '..') {
        return false;
    }

    $realDirectory = realpath($directory);
    if ($realDirectory === false) {
        return false;
    }

    $filePath = $realDirectory . DIRECTORY_SEPARATOR . $filename;
    $realPath = realpath($filePath);

    if ($realPath === false) {
        // The file does not exist. The path is still confined to the directory
        // (basename() stripped any directory parts), so let the caller report 404.
        return $filePath;
    }

    if (strpos($realPath, $realDirectory . DIRECTORY_SEPARATOR) !== 0) {
        return false;
    }

    return $realPath;
}


/**
 * Builds the file info record for one file.
 *
 * With $stat (from scan_pdf_entries) the listing path is taken: no realpath,
 * no extra stat and no finfo, because that costs one open per file and the
 * listing may hold more than a thousand files on a network share. The
 * extension has already been checked and the mimetype is reported as PDF;
 * the single-file endpoints (info, download, rename, delete) verify the
 * mimetype for real.
 */
function file_get_verified_fileinfo($dir, $file, $stat = null) {

    if ($stat === null) {
        $filename = file_get_real_filepath($dir, $file);

        if ($filename === false) {
                send_json_error(400, "No valid file specified");
        }

        if(!file_exists($filename)){
                send_json_error(404, "File does not exist");
        }
        $fileCreationTime = filectime($filename);
        $fileModificationTime = filemtime($filename);
        $finfo = new finfo(FILEINFO_MIME_TYPE);
        $mimetype = $finfo->file($filename);
        $size = filesize($filename);
    } else {
        $filename = rtrim($dir, '/\\') . DIRECTORY_SEPARATOR . basename($file);
        $fileCreationTime = $stat['ctime'];
        $fileModificationTime = $stat['mtime'];
        $mimetype = 'application/pdf';
        $size = $stat['size'];
    }

    $pathInfo = pathinfo($filename);
    $filenameWithoutExtension = pathinfo($filename, PATHINFO_FILENAME);

    $file_info = array(
            'full_path' => $filename,
            'file' => $pathInfo['basename'] ?? '',
            'name' => $filenameWithoutExtension ?? '',
            'name_clean' => '',
            'dir' => $pathInfo['dirname'] ?? '',
            'date_from_name' => '',
            'time_from_name' => '',
            'fileCreationTime' => $fileCreationTime,
            'fileModificationTime' => $fileModificationTime,
            'date_from_file' => date('Y-m-d', $fileModificationTime),
            'time_from_file' => date('H-i-s', $fileModificationTime),
            'extension' => $pathInfo['extension'] ?? '',
            'mimetype' => $mimetype,
            'size' => $size
    );

    if (preg_match('/(\d{4}-\d{2}-\d{2})(?:-(\d{2})(?:-(\d{2})(?:-(\d{2}))?)?)?/', $filename, $matches)) {

            $file_info['date_from_name'] = $matches[1] ?? '';

            if (isset($matches[2])) {
                    $file_info['time_from_name'] = $matches[2] . ':' . ($matches[3] ?? '00') . ':' . ($matches[4] ?? '00');
            }
    }
    // Combine date and time with the dash to form the full datetime string
    $pattern = '/^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\s*/';
    $remove_datetime = $file_info['date_from_name'].'-'.$file_info['time_from_name'];
    $clean_name = preg_replace($pattern, '', $filenameWithoutExtension);

    // Remove only the date and time without extra spaces around
    $remove_date = $file_info['date_from_name'];
    $clean_name = str_replace($remove_date, '', $clean_name);

    $remove_time = $file_info['time_from_name'];
    $clean_name = str_replace($remove_time, '', $clean_name);

    // Trim any remaining leading or trailing spaces
    $clean_name = trim($clean_name);
    $file_info['name_clean'] = $clean_name;

    if($file_info['mimetype'] != 'application/pdf'){
        send_json_error(400, "No valid file specified");
    }


    return $file_info;
}


function file_is_valid_name_string($filename) {

    $pattern = '/[<>:"\/\\|?*\x00-\x1F]/'; // Invalid characters for filenames

    if (preg_match($pattern, $filename)) {
        return false;
    }

    if (strlen($filename) > 255) {
        return false;
    }

    if (strlen($filename) < 3) {
        return false;
    }


    return true;
}


/**
 * One directory read plus one stat per PDF, sorted newest first.
 *
 * Returns array of ['file' => name, 'mtime' => int, 'ctime' => int, 'size' => int].
 * Ties on mtime are broken by name (descending), which for the pipeline's
 * date-stamped names is also newest first.
 */
function scan_pdf_entries($dir) {
    $names = @scandir($dir, SCANDIR_SORT_NONE);
    if ($names === false) {
        return array();
    }
    $base = rtrim($dir, '/\\');
    $entries = array();
    foreach ($names as $name) {
        if ($name === '.' || $name === '..' || $name[0] === '.') {
            continue;
        }
        if (strtolower(pathinfo($name, PATHINFO_EXTENSION)) !== 'pdf') {
            continue;
        }
        $st = @stat($base . DIRECTORY_SEPARATOR . $name);
        if ($st === false || ($st['mode'] & 0170000) !== 0100000) { // regular files only
            continue;
        }
        $entries[] = array('file' => $name, 'mtime' => $st['mtime'], 'ctime' => $st['ctime'], 'size' => $st['size']);
    }
    usort($entries, function($a, $b) {
        $byTime = $b['mtime'] <=> $a['mtime'];
        return $byTime !== 0 ? $byTime : strcmp($b['file'], $a['file']);
    });
    return $entries;
}


/**
 * Lists the PDFs in $dir, newest first.
 *
 * @param string   $dir
 * @param int      $offset  first entry to return
 * @param int|null $limit   number of entries, null for all
 * @param int|null $total   receives the total number of PDFs in the directory
 */
function list_files($dir, $offset = 0, $limit = null, &$total = null){
    $entries = scan_pdf_entries($dir);
    $total = count($entries);
    if ($limit !== null) {
        $entries = array_slice($entries, max(0, $offset), max(0, $limit));
    } elseif ($offset > 0) {
        $entries = array_slice($entries, $offset);
    }

    $data = array();
    foreach ($entries as $entry) {
        $data[] = file_get_verified_fileinfo($dir, $entry['file'], $entry);
    }
    return $data;
}


/**
 * Reads optional offset/limit query parameters: ints, offset >= 0, limit 1..500 or null (all).
 */
function paging_from_query() {
    $query = $_GET;
    if (empty($query) && isset($_SERVER['REQUEST_URI'])) {
        // A rewrite rule in front of index.php may have dropped the query string
        // from $_GET; REQUEST_URI still carries it.
        $raw = parse_url($_SERVER['REQUEST_URI'], PHP_URL_QUERY);
        if (is_string($raw) && $raw !== '') {
            parse_str($raw, $query);
        }
    }
    $offset = isset($query['offset']) && is_numeric($query['offset']) ? max(0, intval($query['offset'])) : 0;
    $limit = null;
    if (isset($query['limit']) && is_numeric($query['limit'])) {
        $limit = max(1, min(500, intval($query['limit'])));
    }
    return array($offset, $limit);
}


/**
 * Job records written by the scan scripts (one JSON file per job in the
 * scanner-jobs directory of the temp dir), enriched with the OCR queue state.
 */
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
function api_token_required() {
    global $API_TOKEN;
    if (!isset($API_TOKEN) || $API_TOKEN === '') {
        return;
    }
    $provided = '';
    $auth = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
    if (stripos($auth, 'Bearer ') === 0) {
        $provided = trim(substr($auth, 7));
    } elseif (isset($_SERVER['HTTP_X_API_TOKEN'])) {
        $provided = $_SERVER['HTTP_X_API_TOKEN'];
    } elseif (isset($_POST['token'])) {
        $provided = $_POST['token'];
    } elseif (isset($_GET['token'])) {
        $provided = $_GET['token'];
    }
    if (!hash_equals($API_TOKEN, (string)$provided)) {
        trigger_error("API request rejected: missing or wrong token from " . ($_SERVER['REMOTE_ADDR'] ?? 'unknown'), E_API);
        send_json_error(401, 'API token required');
    }
}

/** Version string baked into the image (tag, branch-sha or dev). */
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
function thumbnails_enabled() {
    global $GUI_THUMBNAILS;
    if (!isset($GUI_THUMBNAILS)) {
        return true;
    }
    if (is_bool($GUI_THUMBNAILS)) {
        return $GUI_THUMBNAILS;  // config.php and the settings overlay hand booleans over
    }
    return !in_array(strtolower((string)$GUI_THUMBNAILS), array('false', '0', 'no', 'off'));
}

/** Remove cached thumbnails of a file (after rename or delete). */
function thumbnails_forget($filename) {
    foreach (glob('/scans/.thumbnails/' . $filename . '.*.jpg') ?: array() as $old) {
        @unlink($old);
    }
}
?>
