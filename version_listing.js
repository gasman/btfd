$(function() {
    var currentVersion = DOCUMENTATION_OPTIONS.VERSION;
    if (currentVersion.match(/^\d+\.\d+/)) {
        currentVersion = 'v' + currentVersion.replace(/^(\d+\.\d+)(?:\.\d+)?$/, '$1');
    }

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

    function getVersionTuple(versionString) {
        var match = versionString.match(/^v(\d+)\.(\d+)/);
        return [parseInt(match[1], 10), parseInt(match[2], 10)];
    }

    currentVersionTuple = getVersionTuple(currentVersion);
    stableVersion = VERSIONS[2];
    stableVersionTuple = getVersionTuple(stableVersion);

    if (currentVersionTuple < stableVersionTuple) {
        var pathElements = document.location.pathname.split('/');
        pathElements[2] = stableVersion;
        var newUrl = pathElements.join('/');
        newLink = $('<a></a>').text(stableVersion).attr('href', newUrl);

        var message = $('<p class="last">You are not reading the most recent version of this documentation. </p>');
        message.append(newLink, " is the latest version available.");
        var messagePanel = $('<div class="admonition warning"><p class="first admonition-title">Note</p></div>').append(message);
        $('.rst-content > .document').prepend(messagePanel);

    } else if (currentVersionTuple > stableVersionTuple) {
        $('.rst-content > .document').prepend(
            '<div class="admonition warning"><p class="first admonition-title">Note</p><p class="last">This document is for Wagtail\'s development version, which can be significantly different from previous releases. For older releases, use the version selector in the bottom left corner of this page.</p></div>'
        );
    }
});
