<?php
// Thumbnails of the file list: switch, cache lookup, rendering and invalidation.
//
// Layout shared with script/thumbnails.py, which renders ahead of time from the
// pipeline and in a sweep at start:
//   /scans/.thumbnails/<file name>.<mtime>.jpg   (640 x 302, top third of page 1)
// Everything that writes runs as the scan user (UID from config.php) through
// sudo, like the scan triggers, so a volume that only the scan user may write
// to works. When the volume cache cannot be written at all, /tmp/thumbnails
// takes over (lost on restart, but the list keeps its thumbnails).

define('THUMBNAIL_WIDTH', 640);
define('THUMBNAIL_HEIGHT', 302);

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

/** Cache directories in lookup order: the volume, then the container's temp dir. */
function thumbnail_dirs() {
    return array('/scans/.thumbnails', sys_get_temp_dir() . '/thumbnails');
}

/** Cache file name of a file version. */
function thumbnail_stem($file_info) {
    return $file_info['file'] . '.' . $file_info['fileModificationTime'];
}

/**
 * Runs a shell command as the scan user when the web server runs as somebody
 * else. Returns the exit status; $output gets the combined output lines.
 */
function thumbnails_shell($command, &$output = null) {
    global $UID;
    $output = array();
    $prefix = '';
    if (isset($UID) && (int)$UID > 0 && function_exists('posix_geteuid') && posix_geteuid() !== (int)$UID) {
        $prefix = 'sudo -n -u \#' . (int)$UID . ' ';
    }
    exec($prefix . 'sh -c ' . escapeshellarg($command) . ' 2>&1', $output, $status);
    return $status;
}

/** The cached thumbnail of a file version, or null. */
function thumbnail_find($stem) {
    foreach (thumbnail_dirs() as $dir) {
        $candidate = $dir . '/' . $stem . '.jpg';
        if (is_file($candidate) && filesize($candidate) > 0) {
            return $candidate;
        }
    }
    return null;
}

/** Remove cached thumbnails of a file (after rename or delete, or before rendering a new version). */
function thumbnails_forget($filename) {
    $command = 'rm -f';
    foreach (thumbnail_dirs() as $dir) {
        $command .= ' ' . escapeshellarg($dir . '/' . $filename . '.') . '*.jpg';
    }
    thumbnails_shell($command);
}

/**
 * Renders the thumbnail of $pdf into the first writable cache directory.
 * Returns the cache file, or null with the reason in $error.
 */
function thumbnail_render($pdf, $file_info, &$error) {
    $error = '';
    $stem = thumbnail_stem($file_info);
    thumbnails_forget($file_info['file']);
    foreach (thumbnail_dirs() as $dir) {
        $status = thumbnails_shell('mkdir -p ' . escapeshellarg($dir) . ' && test -w ' . escapeshellarg($dir), $output);
        if ($status !== 0) {
            $error = $dir . ' is not writable';
            continue;
        }
        $target = $dir . '/' . $stem . '.jpg';
        $tmpbase = $dir . '/.' . $stem . '.' . getmypid();
        $command = 'timeout 20 pdftoppm -f 1 -l 1'
            . ' -scale-to-x ' . THUMBNAIL_WIDTH . ' -scale-to-y -1 -x 0 -y 0 -W ' . THUMBNAIL_WIDTH . ' -H ' . THUMBNAIL_HEIGHT
            . ' -jpeg -jpegopt quality=70 -singlefile ' . escapeshellarg($pdf) . ' ' . escapeshellarg($tmpbase)
            . ' && mv -f ' . escapeshellarg($tmpbase . '.jpg') . ' ' . escapeshellarg($target)
            . ' && chmod 664 ' . escapeshellarg($target);
        $status = thumbnails_shell($command, $output);
        if ($status === 0 && is_file($target) && filesize($target) > 0) {
            return $target;
        }
        thumbnails_shell('rm -f ' . escapeshellarg($tmpbase . '.jpg'));
        $error = trim(implode(' ', array_slice($output, -3)));
        if ($error === '') {
            $error = 'exit status ' . $status;
        }
        break;  // the directory was writable, so the PDF itself is the problem
    }
    return null;
}
?>
