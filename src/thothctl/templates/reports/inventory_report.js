// Navigation and Interactivity JavaScript for Inventory Reports
document.addEventListener('DOMContentLoaded', function() {
    // Initialize collapsible sections
    initializeCollapsibleSections();
    
    // Initialize back to top button
    initializeBackToTop();
    
    // Initialize smooth scrolling for navigation links
    initializeSmoothScrolling();
    
    // Add click tracking for analytics (optional)
    trackUserInteractions();
});

function initializeCollapsibleSections() {
    // Make stack headers collapsible
    const stackHeaders = document.querySelectorAll('.stack-header');
    stackHeaders.forEach(header => {
        // Add expand icon to stack headers
        const expandIcon = document.createElement('span');
        expandIcon.className = 'expand-icon';
        expandIcon.innerHTML = '▼';
        expandIcon.style.marginLeft = '10px';
        header.appendChild(expandIcon);
        
        header.addEventListener('click', function() {
            toggleStackSection(this);
        });
    });
}

function toggleStackSection(header) {
    const stackSection = header.parentElement;
    const content = stackSection.querySelector('.table-section')?.parentElement || 
                   stackSection.querySelector('.collapsible-content');
    const icon = header.querySelector('.expand-icon');
    
    if (content) {
        // Create collapsible wrapper if it doesn't exist
        if (!content.classList.contains('collapsible-content')) {
            const wrapper = document.createElement('div');
            wrapper.className = 'collapsible-content';
            content.parentNode.insertBefore(wrapper, content);
            wrapper.appendChild(content);
        }
        
        const wrapper = content.classList.contains('collapsible-content') ? content : content.parentElement;
        wrapper.classList.toggle('collapsed');
        icon.classList.toggle('rotated');
    }
}

function toggleAllSections() {
    const allStackSections = document.querySelectorAll('.stack-section');
    const toggleText = document.getElementById('toggle-all-text');
    const toggleIcon = document.getElementById('toggle-all-icon');
    const isCollapsed = toggleText.textContent === 'Expand All';
    
    allStackSections.forEach(section => {
        const content = section.querySelector('.collapsible-content') || 
                      section.querySelector('.table-section')?.parentElement;
        const icon = section.querySelector('.stack-header .expand-icon');
        
        if (content) {
            // Create collapsible wrapper if it doesn't exist
            if (!content.classList.contains('collapsible-content')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'collapsible-content';
                content.parentNode.insertBefore(wrapper, content);
                wrapper.appendChild(content);
            }
            
            const wrapper = content.classList.contains('collapsible-content') ? content : content.parentElement;
            
            if (isCollapsed) {
                wrapper.classList.remove('collapsed');
                if (icon) icon.classList.remove('rotated');
            } else {
                wrapper.classList.add('collapsed');
                if (icon) icon.classList.add('rotated');
            }
        }
    });
    
    // Update toggle button text
    toggleText.textContent = isCollapsed ? 'Collapse All' : 'Expand All';
    toggleIcon.textContent = isCollapsed ? '▼' : '▲';
}

function initializeBackToTop() {
    const backToTopButton = document.getElementById('backToTop');
    
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            backToTopButton.classList.add('visible');
        } else {
            backToTopButton.classList.remove('visible');
        }
    });
}

function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

function initializeSmoothScrolling() {
    const navLinks = document.querySelectorAll('.nav-link[href^="#"]');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            const targetElement = document.getElementById(targetId);
            
            if (targetElement) {
                const offsetTop = targetElement.offsetTop - 80; // Account for sticky header
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
            }
        });
    });
}

function trackUserInteractions() {
    // Track section expansions
    document.addEventListener('click', function(e) {
        if (e.target.closest('.stack-header')) {
            const stackTitle = e.target.closest('.stack-section')?.querySelector('.stack-title')?.textContent;
            console.log('Stack section toggled:', stackTitle);
        }
        
        if (e.target.closest('.nav-link')) {
            console.log('Navigation clicked:', e.target.textContent);
        }
    });
}

// Compatibility section toggle functions
function toggleCompatibilitySection() {
    const content = document.getElementById('compatibility-content');
    const icon = document.getElementById('compatibility-icon');
    
    if (content && icon) {
        if (content.style.maxHeight === '0px' || content.style.opacity === '0') {
            // Expand
            content.style.maxHeight = '2000px';
            content.style.opacity = '1';
            icon.style.transform = 'rotate(0deg)';
            icon.textContent = '▼';
        } else {
            // Collapse
            content.style.maxHeight = '0px';
            content.style.opacity = '0';
            icon.style.transform = 'rotate(-90deg)';
            icon.textContent = '▶';
        }
    }
}

function toggleProviderCompatibility(providerId) {
    const content = document.getElementById(providerId + '-content');
    const icon = document.getElementById(providerId + '-icon');
    
    if (content && icon) {
        if (content.style.maxHeight === '0px' || content.style.opacity === '0') {
            // Expand
            content.style.maxHeight = '1000px';
            content.style.opacity = '1';
            icon.style.transform = 'rotate(0deg)';
            icon.textContent = '▼';
        } else {
            // Collapse
            content.style.maxHeight = '0px';
            content.style.opacity = '0';
            icon.style.transform = 'rotate(-90deg)';
            icon.textContent = '▶';
        }
    }
}

// Enhanced keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Escape to collapse all sections
    if (e.key === 'Escape') {
        const expandedSections = document.querySelectorAll('.collapsible-content:not(.collapsed)');
        if (expandedSections.length > 0) {
            toggleAllSections();
        }
        
        // Also collapse compatibility sections
        const compatibilityContent = document.getElementById('compatibility-content');
        if (compatibilityContent && compatibilityContent.style.maxHeight !== '0px') {
            toggleCompatibilitySection();
        }
    }
    
    // Home key to scroll to top
    if (e.key === 'Home' && e.ctrlKey) {
        e.preventDefault();
        scrollToTop();
    }
    
    // 'C' key to toggle compatibility section
    if (e.key === 'c' || e.key === 'C') {
        if (!e.ctrlKey && !e.altKey && !e.metaKey) {
            const compatibilitySection = document.querySelector('.compatibility-section');
            if (compatibilitySection) {
                toggleCompatibilitySection();
            }
        }
    }
});

// Add section anchors for better navigation
function addSectionAnchors() {
    const stackSections = document.querySelectorAll('.stack-section');
    stackSections.forEach((section, index) => {
        const title = section.querySelector('.stack-title');
        if (title) {
            const anchor = title.textContent.toLowerCase().replace(/[^a-z0-9]+/g, '-');
            section.id = `stack-${index}-${anchor}`;
            
            // Add anchor link to title
            const anchorLink = document.createElement('a');
            anchorLink.href = `#${section.id}`;
            anchorLink.style.color = 'inherit';
            anchorLink.style.textDecoration = 'none';
            anchorLink.innerHTML = title.innerHTML;
            title.innerHTML = '';
            title.appendChild(anchorLink);
        }
    });
}

// Initialize section anchors after DOM is loaded
document.addEventListener('DOMContentLoaded', addSectionAnchors);
