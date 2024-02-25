<?php

// Define constants for sorting flags
define('GETFILELIST_SORT_NAME_ASC', 1);
define('GETFILELIST_SORT_NAME_DESC', 2);
define('GETFILELIST_SORT_CREATEDATE_ASC', 4);
define('GETFILELIST_SORT_CREATEDATE_DESC', 8);
define('GETFILELIST_SORT_MODIFYDATE_ASC', 16);
define('GETFILELIST_SORT_MODIFYDATE_DESC', 32);
define('GETFILELIST_SORT_DIRNAME_ASC', 64);
define('GETFILELIST_SORT_DIRNAME_DESC', 128);

function getFileList($path, $sortFlags = GETFILELIST_SORT_NAME_ASC) {
    // Check if the directory exists
    if (!is_dir($path)) {
        return [];
    }

    $files = [];

    // Helper function to sort by various criteria
    $sortFunction = function ($a, $b) use ($sortFlags) {
        if ($sortFlags & GETFILELIST_SORT_NAME_ASC || $sortFlags & GETFILELIST_SORT_NAME_DESC) {
            return strnatcasecmp($a, $b);
        } elseif ($sortFlags & GETFILELIST_SORT_CREATEDATE_ASC) {
            return filectime($a) - filectime($b);
        } elseif ($sortFlags & GETFILELIST_SORT_CREATEDATE_DESC) {
            return filectime($b) - filectime($a);
        } elseif ($sortFlags & GETFILELIST_SORT_MODIFYDATE_ASC) {
            return filemtime($a) - filemtime($b);
        } elseif ($sortFlags & GETFILELIST_SORT_MODIFYDATE_DESC) {
            return filemtime($b) - filemtime($a);
        } elseif ($sortFlags & GETFILELIST_SORT_DIRNAME_ASC) {
            return strnatcasecmp(dirname($a), dirname($b));
        } elseif ($sortFlags & GETFILELIST_SORT_DIRNAME_DESC) {
            return strnatcasecmp(dirname($b), dirname($a));
        }
        return strnatcasecmp($a, $b); // Default sort by name
    };

    // Helper function to recursively iterate over directories
    $iterateDir = function ($dir) use (&$files, &$iterateDir, $sortFlags, $sortFunction) {
        $contents = scandir($dir);
        if ($contents === false) {
            return;
        }
        foreach ($contents as $item) {
            if ($item == '.' || $item == '..') {
                continue;
            }
            $fullPath = $dir . DIRECTORY_SEPARATOR . $item;
            if (is_dir($fullPath)) {
                $iterateDir($fullPath);
            } else {
                $files[] = $fullPath;
            }
        }
    };

    $iterateDir($path);

    // Sorting
    usort($files, $sortFunction);

    return $files;
}

?>