<?php
include('config.php');
require_once('helper.php');

// GET /api/file/<name>/thumbnail: a small JPEG of the first page.
//
// Rendered once per file (pdftoppm, first page, 20 dpi) and cached on the
// volume under /scans/.thumbnails/<name>.<mtime>.jpg, so a listing request
// never renders anything and a changed file gets a new thumbnail. Served with
// an ETag and a long cache lifetime; a PDF that cannot be rendered answers a
// placeholder image instead of an error so the list keeps working.

$THUMB_DIR = '/scans/.thumbnails';
$PLACEHOLDER = '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="128" viewBox="0 0 96 128">'
    . '<rect width="96" height="128" fill="#e9ecef"/>'
    . '<path d="M28 20h28l16 16v72H28z" fill="#fff" stroke="#adb5bd" stroke-width="2"/>'
    . '<path d="M56 20v16h16" fill="none" stroke="#adb5bd" stroke-width="2"/>'
    . '<path d="M36 56h28M36 68h28M36 80h18" stroke="#ced4da" stroke-width="3"/>'
    . '</svg>';

if (!isset($file)) {
    send_json_error(400, 'No file specified');
}
if (!thumbnails_enabled()) {
    send_json_error(404, 'Thumbnails are disabled (GUI_THUMBNAILS=false)');
}

$info = file_get_verified_fileinfo('/scans/', urldecode($file));
$stem = $info['file'] . '.' . $info['fileModificationTime'];
$thumb = $THUMB_DIR . '/' . $stem . '.jpg';
$etag = '"' . md5($stem) . '"';

if (isset($_SERVER['HTTP_IF_NONE_MATCH']) && trim($_SERVER['HTTP_IF_NONE_MATCH']) === $etag) {
    http_response_code(304);
    header('ETag: ' . $etag);
    exit;
}

$cache = 'hit';
if (!is_file($thumb)) {
    $cache = 'miss';
    if (!is_dir($THUMB_DIR)) {
        @mkdir($THUMB_DIR, 0777, true);
    }
    // Stale thumbnails of an earlier version of this file
    foreach (glob($THUMB_DIR . '/' . $info['file'] . '.*.jpg') ?: array() as $old) {
        @unlink($old);
    }
    $tmpbase = $THUMB_DIR . '/.' . $stem . '.' . getmypid();
    $command = 'timeout 20 pdftoppm -f 1 -l 1 -r 20 -jpeg -jpegopt quality=70 -singlefile '
        . escapeshellarg($info['full_path']) . ' ' . escapeshellarg($tmpbase) . ' 2>&1';
    exec($command, $output, $status);
    if ($status === 0 && is_file($tmpbase . '.jpg') && filesize($tmpbase . '.jpg') > 0) {
        @rename($tmpbase . '.jpg', $thumb);
        @chmod($thumb, 0664);
    } else {
        @unlink($tmpbase . '.jpg');
        trigger_error('thumbnail failed for ' . $info['file'] . ': ' . implode(' ', array_slice($output, -3)), E_API);
        header('Content-Type: image/svg+xml');
        header('Cache-Control: public, max-age=3600');
        header('X-Thumbnail-Cache: placeholder');
        echo $PLACEHOLDER;
        exit;
    }
}

header('Content-Type: image/jpeg');
header('Content-Length: ' . filesize($thumb));
header('ETag: ' . $etag);
header('Cache-Control: public, max-age=31536000, immutable');
header('X-Thumbnail-Cache: ' . $cache);
readfile($thumb);
exit;
?>
