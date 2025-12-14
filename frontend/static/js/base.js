document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const links = document.querySelectorAll('.nav-link');
    const overlay = document.querySelector('.sidebar-overlay');
    const mobileToggle = document.querySelector('.mobile-toggle');

    function isMobile() {
        return window.innerWidth <= 768;
    }

    function applySidebarState(isCollapsed) {
        if (isMobile()) {
            sidebar.classList.remove('collapsed');
            mainContent.classList.remove('expanded');
        } else {
            if (isCollapsed) {
                sidebar.classList.add('collapsed');
                mainContent.classList.add('expanded');
            } else {
                sidebar.classList.remove('collapsed');
                mainContent.classList.remove('expanded');
            }
        }
    }

    // restore sidebar state
    const savedState = localStorage.getItem('sidebar-collapsed');
    if (savedState === 'true') {
        applySidebarState(true);
    }

    // nav link active state
    links.forEach(link => {
        if (link.href === window.location.href) {
            link.classList.add('active');
        }
    });

    // desktop toggle via header icon
    const desktopToggle = document.querySelector('.logo-icon');
    if (desktopToggle) {
        desktopToggle.addEventListener('click', () => {
            const collapsed = sidebar.classList.toggle('collapsed');
            mainContent.classList.toggle('expanded');
            localStorage.setItem('sidebar-collapsed', collapsed);
        });
    }

    // mobile toggle button
    if (mobileToggle) {
        mobileToggle.addEventListener('click', () => {
            sidebar.classList.add('show');
            overlay.classList.add('show');
        });
    }

    // close sidebar when clicking overlay on mobile
    if (overlay) {
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('show');
            overlay.classList.remove('show');
        });
    }

    // resize handler to reset overlay state when switching between mobile/desktop
    window.addEventListener('resize', () => {
        if (!isMobile()) {
            sidebar.classList.remove('show');
            overlay.classList.remove('show');
            const collapsed = localStorage.getItem('sidebar-collapsed') === 'true';
            applySidebarState(collapsed);
        }
    });
});
