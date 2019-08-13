$(function() {
    var currentVersion = DOCUMENTATION_OPTIONS.VERSION;
    currentVersion = currentVersion.replace(/^(\d+\.\d+)(?:\.\d+)?$/, 'v$1');

    var versionsPanel = $('<div class="rst-versions" role="note" aria-label="versions"></div>');
    var currentVersionLabel = $('<span class="rst-current-version"></span>').text('v: ' + currentVersion).append(' <span class="fa fa-caret-down"></span>');

    var otherVersionsPanel = $('<div class="rst-other-versions"></div>');
    var versionsList = $('<dl><dt>Versions</dt></dl>');
    for (var i = 0; i < VERSIONS.length; i++) {
        var version = VERSIONS[i];
        var versionLabel = $('<dd><a></a></dd>');
        $('a', versionLabel).attr('href', '/en/' + version + '/').text(version);
        versionsList.append(versionLabel);
        if (version == currentVersion) {
            versionLabel.wrap('<strong></strong>');
        }
    }
    otherVersionsPanel.append(versionsList);

    versionsPanel.append(currentVersionLabel, otherVersionsPanel);
    $('body').append(versionsPanel);
    currentVersionLabel.click(function() {
        otherVersionsPanel.toggle();
    });
});
