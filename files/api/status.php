<?php
include_once(__DIR__."/lib/config.php");

exec("ps aux | grep '[s]canimage'", $output, $retVal);
if(!empty($output)) {
    echo("scanning");
} else {
    if (str_contains(file_get_contents(__DIR__ . '/reachable.txt'), '1')) {
        echo("online");
    } else {
        echo("offline");
    }
}
?>