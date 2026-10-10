<?php
include('config.php');
require_once('helper.php');

$files = list_files('/scans/');

json($files);

?>