<?php
// Thumbnail switch and cache invalidation for the file list.

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
