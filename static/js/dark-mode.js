/**
 * Dark mode toggle – persists in localStorage, applies class on <html>
 */
(function () {
    var STORAGE_KEY = 'dark_mode';

    function isDark() {
        try {
            return localStorage.getItem(STORAGE_KEY) === '1';
        } catch (e) {
            return false;
        }
    }

    function setDark(on) {
        try {
            localStorage.setItem(STORAGE_KEY, on ? '1' : '0');
        } catch (e) {}
        var root = document.documentElement;
        if (on) {
            root.classList.add('dark-mode');
        } else {
            root.classList.remove('dark-mode');
        }
        updateIcon();
    }

    function updateIcon() {
        var btn = document.getElementById('darkModeBtn');
        if (!btn) return;
        var icon = btn.querySelector('i');
        if (!icon) return;
        if (isDark()) {
            icon.classList.remove('fa-moon');
            icon.classList.add('fa-sun');
            btn.setAttribute('title', 'Switch to light mode');
            btn.setAttribute('aria-label', 'Switch to light mode');
        } else {
            icon.classList.remove('fa-sun');
            icon.classList.add('fa-moon');
            btn.setAttribute('title', 'Switch to dark mode');
            btn.setAttribute('aria-label', 'Switch to dark mode');
        }
    }

    function initNav() {
        var toggle = document.getElementById('navToggle');
        var nav = document.querySelector('.main-nav');
        if (!toggle || !nav) return;

        toggle.addEventListener('click', function (e) {
            e.stopPropagation();
            nav.classList.toggle('open');
        });

        document.addEventListener('click', function (e) {
            if (!nav.contains(e.target) && !toggle.contains(e.target)) {
                nav.classList.remove('open');
            }
        });
    }

    function init() {
        setDark(isDark());
        var btn = document.getElementById('darkModeBtn');
        if (btn) {
            btn.addEventListener('click', function () {
                setDark(!isDark());
            });
        }
        initNav();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
