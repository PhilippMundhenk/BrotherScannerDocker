<?php

function json($data){

    header('Content-Type: application/json');
    print_r(json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    die();

}


function send_json_error($http_code, $message){

    header('Content-Type: application/json');
    http_response_code($http_code);
    json(array('code' => $http_code, 'message' => $message));
    die();
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
    $offset = isset($_GET['offset']) && is_numeric($_GET['offset']) ? max(0, intval($_GET['offset'])) : 0;
    $limit = null;
    if (isset($_GET['limit']) && is_numeric($_GET['limit'])) {
        $limit = max(1, min(500, intval($_GET['limit'])));
    }
    return array($offset, $limit);
}
?>
