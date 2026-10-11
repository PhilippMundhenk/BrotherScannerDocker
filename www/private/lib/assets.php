<?php
// Static assets of the web UI.

/**
 * URL of a static asset with a cache-busting version: the file's modification
 * time, which every image build sets anew, so a browser never keeps the
 * scripts or styles of an earlier version after an update (#144).
 */
function asset_url($path) {
    $mtime = @filemtime('/var/www/html' . $path);
    return $path . '?v=' . ($mtime === false ? rawurlencode(container_version()) : $mtime);
}
?>
