<div class="d-flex flex-column align-items-stretch flex-shrink-0 bg-white" >

<div class="list-group list-group-flush border-bottom scrollarea">

<?php
// Directory path
$directory = '/scans';

// Get list of files and directories
$files = scandir($directory);

// Remove '.' and '..' from the list
$files = array_diff($files, array('.', '..'));

// Create an associative array with filenames and their modification times
$filesWithMtime = array();
foreach ($files as $file) {
    $filePath = $directory . '/' . $file;
    if (is_file($filePath) && pathinfo($filePath, PATHINFO_EXTENSION) === 'pdf') { // Filter PDF files
        $filesWithMtime[$file] = array(
            'mtime' => filemtime($filePath),
            'size' => filesize($filePath),
            'permissions' => substr(sprintf('%o', fileperms($filePath)), -4),
            'owner' => posix_getpwuid(fileowner($filePath))['name'],
            'group' => posix_getgrgid(filegroup($filePath))['name'],
        );
    }
}

// Sort files by modification time (newest first)
uasort($filesWithMtime, function($a, $b) {
    return $b['mtime'] <=> $a['mtime'];
});

// Output sorted files
foreach ($filesWithMtime as $file => $attributes) {
?>
  <a href="/download.php?file=<?php echo $file; ?>" class="list-group-item list-group-item-action py-3 lh-tight" target="_blank"aria-current="true">
    <div class="d-flex w-100 align-items-center justify-content-between">
      <strong class="mb-1"><?php echo $file; ?></strong>
      <small><?php echo date('D', $mtime); ?></small>
    </div>
    <div class="col-12 mb-1 small"><?php echo number_format($attributes['size']); ?> Bytes</div>
  </a>
<?php

}
?>


  
</div>
</div>


