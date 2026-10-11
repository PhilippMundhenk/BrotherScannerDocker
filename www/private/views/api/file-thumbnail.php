<?php
include('config.php');
require_once('helper.php');

// GET /api/file/<name>/thumbnail: a landscape JPEG of the top third of the
// first page (640 x 302) for the file list.
//
// Normally the pipeline has rendered it already (script/thumbnails.py, right
// after a scan and in a sweep at start); otherwise it is rendered here, as the
// scan user, and cached under /scans/.thumbnails/<name>.<mtime>.jpg (fallback
// /tmp/thumbnails when the volume cache cannot be written), so a listing
// request never renders anything twice and a changed file gets a new
// thumbnail. Served with an ETag and a long cache lifetime; a PDF that cannot
// be rendered answers a placeholder image instead of an error, with the reason
// in X-Thumbnail-Error, so the list keeps working.

$PLACEHOLDER = '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="302" viewBox="0 0 640 302">'
    . '<rect width="640" height="302" fill="#e9ecef"/>'
    . '<path d="M284 95h56l32 32v80h-88z" fill="#fff" stroke="#adb5bd" stroke-width="4"/>'
    . '<path d="M340 95v32h32" fill="none" stroke="#adb5bd" stroke-width="4"/>'
    . '<path d="M300 150h56M300 168h56M300 186h36" stroke="#ced4da" stroke-width="5"/>'
    . '</svg>';

if (!isset($file)) {
    send_json_error(400, 'No file specified');
}
if (!thumbnails_enabled()) {
    send_json_error(404, 'Thumbnails are disabled (GUI_THUMBNAILS=false)');
}

$info = file_get_verified_fileinfo('/scans/', urldecode($file));
$stem = thumbnail_stem($info);
$etag = '"' . md5($stem) . '"';

if (isset($_SERVER['HTTP_IF_NONE_MATCH']) && trim($_SERVER['HTTP_IF_NONE_MATCH']) === $etag) {
    http_response_code(304);
    header('ETag: ' . $etag);
    exit;
}

$cache = 'hit';
$thumb = thumbnail_find($stem);
if ($thumb === null) {
    $cache = 'miss';
    $thumb = thumbnail_render($info['full_path'], $info, $error);
    if ($thumb === null) {
        trigger_error('thumbnail failed for ' . $info['file'] . ': ' . $error, E_API);
        header('Content-Type: image/svg+xml');
        header('Cache-Control: public, max-age=3600');
        header('X-Thumbnail-Cache: placeholder');
        header('X-Thumbnail-Error: ' . substr(preg_replace('/[^\x20-\x7e]+/', ' ', $error), 0, 200));
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
