<?php
include_once(__DIR__."/lib/config.php");

$status_file=__DIR__ . '/reachable.txt';

exec("ps aux | grep '[s]canimage'", $output, $retVal);
if(!empty($output)) {
    echo("scanning");
} else {
	if (!file_exists($status_file)) {
		echo("unknown");
        return;
	}
    if (str_contains(file_get_contents($status_file), '1')) {
        echo("online");
    } else {
        echo("offline");
    }
}
?>