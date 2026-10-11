<?php
include('config.php');
require_once('helper.php');
require_once('settings.php');

if (!settings_enabled()) {
    send_error_page(403, $page_title = 'Settings disabled', $page_message = 'Set ALLOW_GUI_SETTINGS=true to enable the settings page.');
}

$groups = array();
foreach (settings_all() as $item) {
    $groups[$item['group']][] = $item;
}
?>
<!DOCTYPE html>
<html>

<head>
    <?php include('views/frontend/common-head.php'); ?>
    <title>Settings - Brother <?php echo($MODEL); ?></title>
    <?php if (isset($API_TOKEN) && $API_TOKEN !== '') { ?>
    <meta name="api-token" content="<?php echo htmlspecialchars($API_TOKEN); ?>">
    <?php } ?>
</head>

<body class="bg-dark text-light">

    <nav class="navbar navbar-expand-sm fixed-top navbar-dark bg-dark">
        <div class="container pe-0">
            <a class="navbar-brand" href="/"><?php echo($MODEL); ?></a>
            <a class="nav-link text-white me-0" href="/" title="Back to the scanner"><i class="fas fa-home fa-fw fa-2x"></i></a>
        </div>
    </nav>

    <section class="pt-5 pb-5 mt-4">
        <div class="container" style="max-width: 900px;">
            <h1 class="h3 mb-1">Settings</h1>
            <p class="small text-white-50 mb-2" id="settings-file">
                This page writes <code><?php echo htmlspecialchars(settings_config_path()); ?></code> on the scans volume.
                Settings marked <span class="badge bg-warning text-dark">restart</span> take effect after a container restart.
            </p>
            <p class="small text-white-50 mb-4" id="settings-sources">
                Every value comes from one of three places, in this order of precedence:
                <span class="badge bg-info text-dark">environment</span> the container environment, i.e. the <code>environment:</code> block of your docker-compose file or <code>docker run -e</code>;
                it always wins, so such values are read-only here &ndash; change them in the compose file, or remove them there (and restart) to manage them on this page.
                <span class="badge bg-success">file</span> the configuration file above, written by this page.
                No badge: the built-in default, shown as placeholder.
            </p>

            <form id="settings-form" autocomplete="off">
            <?php foreach ($groups as $group => $items) { ?>
                <div class="card bg-secondary text-light mb-3">
                    <div class="card-header fw-bold"><?php echo htmlspecialchars($group); ?></div>
                    <div class="card-body">
                    <?php foreach ($items as $item) {
                        $id = 'setting-' . $item['key'];
                        $disabled = $item['locked'] ? ' disabled' : '';
                    ?>
                        <div class="row mb-3 align-items-center setting-row" data-key="<?php echo $item['key']; ?>" data-type="<?php echo $item['type']; ?>" data-locked="<?php echo $item['locked'] ? '1' : '0'; ?>" id="row-<?php echo $item['key']; ?>">
                            <label class="col-sm-5 col-form-label" for="<?php echo $id; ?>">
                                <code class="text-light"><?php echo $item['key']; ?></code>
                                <?php if ($item['restart']) { ?><span class="badge bg-warning text-dark ms-1">restart</span><?php } ?>
                                <?php if ($item['locked']) { ?><span class="badge bg-info text-dark ms-1" title="Set in the container environment">environment</span><?php } ?>
                                <?php if ($item['source'] === 'file') { ?><span class="badge bg-success ms-1 source-badge">file</span><?php } ?>
                                <div class="small text-white-50 fw-normal"><?php echo htmlspecialchars($item['description']); ?></div>
                            </label>
                            <div class="col-sm-7">
                            <?php if ($item['type'] === 'bool') { ?>
                                <select class="form-select form-select-sm setting-input" id="<?php echo $id; ?>" name="<?php echo $item['key']; ?>"<?php echo $disabled; ?>>
                                    <option value="true"<?php echo strtolower((string)$item['value']) === 'true' ? ' selected' : ''; ?>>true</option>
                                    <option value="false"<?php echo strtolower((string)$item['value']) !== 'true' ? ' selected' : ''; ?>>false</option>
                                </select>
                            <?php } elseif ($item['type'] === 'secret') { ?>
                                <input class="form-control form-control-sm setting-input" type="password" id="<?php echo $id; ?>" name="<?php echo $item['key']; ?>" value="" placeholder="<?php echo $item['is_set'] ? '(set, leave empty to keep)' : '(not set)'; ?>"<?php echo $disabled; ?>>
                            <?php } else { ?>
                                <input class="form-control form-control-sm setting-input" type="text" id="<?php echo $id; ?>" name="<?php echo $item['key']; ?>" value="<?php echo htmlspecialchars((string)$item['value']); ?>" placeholder="<?php echo htmlspecialchars((string)$item['default']); ?>"<?php echo $disabled; ?>>
                            <?php } ?>
                                <div class="invalid-feedback setting-error"></div>
                            </div>
                        </div>
                    <?php } ?>
                    </div>
                </div>
            <?php } ?>
                <div class="d-flex align-items-center gap-3 mt-3 mb-5">
                    <button type="submit" class="btn btn-light" id="settings-save">Save</button>
                    <span id="settings-result" class="small"></span>
                </div>
            </form>

            <!-- Migration from environment variables to the file (#161) -->
            <div class="card bg-secondary text-light mb-5" id="import-environment-card">
                <div class="card-header fw-bold">Move settings from the environment into the file</div>
                <div class="card-body">
                    <p class="small mb-3">
                        Copies every value marked <span class="badge bg-info text-dark">environment</span>, passwords and tokens included, into the configuration file.
                        The environment still wins afterwards: remove the entries from your compose file and restart the container, and the file carries on with the same values, editable here.
                    </p>
                    <div class="d-flex align-items-center gap-3">
                        <button type="button" class="btn btn-outline-light" id="import-environment">Copy environment values into the file</button>
                        <span id="import-result" class="small"></span>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <?php include('views/frontend/common-javascript.php'); ?>
    <script>
    (function () {
        var token = $('meta[name="api-token"]').attr('content');
        if (token) { $.ajaxSetup({ headers: { 'X-API-Token': token } }); }
    })();

    // Only values the user changed are sent; an empty text field means
    // "remove from the file" (back to environment or default). Secrets are
    // sent only when something was typed.
    var original = {};
    $('.setting-input').each(function () { original[this.name] = $(this).val(); });

    $('#import-environment').on('click', function () {
        var result = $('#import-result');
        if (!window.confirm('Copy every value set by the environment, passwords and tokens included, into the configuration file?')) { return; }
        $.ajax({
            url: '/api/settings/import-environment', type: 'POST',
            success: function (data) {
                var text;
                if (data.environment.length === 0) {
                    text = data.message + '.';
                } else {
                    text = 'Copied: ' + (data.written.join(', ') || 'nothing new') +
                        (data.unchanged.length ? ' (already in the file: ' + data.unchanged.join(', ') + ')' : '') +
                        '. Now remove from the compose file and restart: ' + data.environment.join(', ') + '.';
                }
                result.text(text).removeClass('text-danger').addClass('text-success');
            },
            error: function (xhr) {
                var body = xhr.responseJSON || {};
                result.text(body.message || 'Copying failed (' + xhr.status + ')').removeClass('text-success').addClass('text-danger');
            }
        });
    });

    $('#settings-form').on('submit', function (e) {
        e.preventDefault();
        var changes = {};
        $('.setting-input').each(function () {
            var row = $(this).closest('.setting-row');
            if (row.data('locked') === 1) { return; }
            var value = $(this).val();
            if (row.data('type') === 'secret') {
                if (value !== '') { changes[this.name] = value; }
                return;
            }
            if (value !== original[this.name]) { changes[this.name] = value; }
        });
        $('.setting-input').removeClass('is-invalid');
        var result = $('#settings-result');
        if (Object.keys(changes).length === 0) {
            result.text('Nothing changed.').removeClass('text-danger').addClass('text-white-50');
            return;
        }
        $.ajax({
            url: '/api/settings', type: 'PUT', contentType: 'application/json', data: JSON.stringify(changes),
            success: function (data) {
                var text = 'Saved: ' + (data.saved.concat(data.removed.map(function (k) { return k + ' (removed)'; })).join(', ') || 'nothing');
                if (data.restart_required.length > 0) {
                    text += '. Restart the container for: ' + data.restart_required.join(', ') + '.';
                }
                result.text(text).removeClass('text-danger text-white-50').addClass('text-success');
                $('.setting-input').each(function () {
                    var row = $(this).closest('.setting-row');
                    if (row.data('type') === 'secret') { $(this).val(''); return; }
                    original[this.name] = $(this).val();
                });
                data.settings.forEach(function (item) {
                    var label = $('#row-' + item.key + ' label');
                    label.find('.source-badge').remove();
                    if (item.source === 'file') {
                        label.find('.small').before('<span class="badge bg-success ms-1 source-badge">file</span>');
                    }
                });
            },
            error: function (xhr) {
                var body = xhr.responseJSON || {};
                var errors = body.errors || {};
                Object.keys(errors).forEach(function (key) {
                    var input = $('#setting-' + key);
                    input.addClass('is-invalid');
                    input.siblings('.setting-error').text(errors[key]);
                });
                result.text(body.message || 'Saving failed (' + xhr.status + ')').removeClass('text-success text-white-50').addClass('text-danger');
            }
        });
    });
    </script>
</body>

</html>
