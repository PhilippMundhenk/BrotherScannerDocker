<?php

function is_sub_path($path, $parent_folder) {
    $path = realpath($path);
    $parrent_foler = realpath($parent_folder);

    if ($path !== false && $parent_folder !== false) {
        return strpos($path, $parent_folder) === 0;
    }

    return false;
}
?>