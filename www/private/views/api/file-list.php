<?php
include('config.php');
require_once('helper.php');

// GET /api/file-list[?offset=N&limit=M]
// Newest first. Without limit the whole list is returned (as before); with
// limit the response is one page and X-Total-Count carries the total.
list($offset, $limit) = paging_from_query();
$total = 0;
$files = list_files('/scans/', $offset, $limit, $total);

header('X-Total-Count: ' . $total);
header('X-Offset: ' . $offset);
if ($limit !== null) {
    header('X-Limit: ' . $limit);
}

json($files);

?>
