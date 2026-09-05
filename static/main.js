// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', function() {

  // Elements
  const searchToggle = document.getElementById('search-toggle');
  const searchBar = document.getElementById('search-bar');
  const searchInput = document.getElementById('search-input');
  const searchForm = document.getElementById('search-form');
  const searchClose = document.getElementById('search-close');
  const noResultsDiv = document.getElementById('no-results');
  const categoryButtons = document.querySelectorAll('.category-btn');
  const products = document.querySelectorAll('.product');

  // Function to filter products based on search and category
  function filterProducts() {
    const query = searchInput.value.toLowerCase().trim();
    const activeCategory = document.querySelector('.category-btn.active')?.dataset.category || 'all';
    let visibleCount = 0;

    products.forEach(product => {
      const name = product.dataset.name || '';
      const description = product.dataset.description || '';
      const matchesSearch = name.includes(query) || description.includes(query);
      const matchesCategory = activeCategory === 'all' || product.dataset.category === activeCategory;

      if (matchesSearch && matchesCategory) {
        product.style.display = '';
        visibleCount++;
      } else {
        product.style.display = 'none';
      }
    });

    if (noResultsDiv) {
      noResultsDiv.style.display = visibleCount === 0 ? 'block' : 'none';
    }
  }

  // Open search bar
  function openSearch() {
    searchBar.classList.add('open');
    searchBar.style.display = 'block';
    searchInput.focus();
  }

  // Close search bar
  function closeSearch() {
    searchBar.classList.remove('open');
    searchBar.style.display = 'none';
    searchInput.value = '';
    filterProducts(); // Show all products again
  }

  // Toggle search bar on icon click
  searchToggle.addEventListener('click', function(e) {
    e.preventDefault();
    if (searchBar.classList.contains('open')) {
      closeSearch();
    } else {
      openSearch();
    }
  });

  // Close search bar on close button click
  searchClose.addEventListener('click', function() {
    closeSearch();
  });

  // Close search bar on Escape key
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && searchBar.classList.contains('open')) {
      closeSearch();
    }
  });

  // Search input event
  searchInput.addEventListener('input', filterProducts);

  // Prevent form submission (Enter key)
  searchForm.addEventListener('submit', function(e) {
    e.preventDefault();
    filterProducts();
  });

  // Category filter
  categoryButtons.forEach(button => {
    button.addEventListener('click', function() {
      categoryButtons.forEach(btn => btn.classList.remove('active'));
      this.classList.add('active');
      searchInput.value = '';
      filterProducts();
    });
  });

  // Mobile menu
  const menuBtn = document.querySelector('.menu-btn');
  const nav = document.querySelector('.nav');

  menuBtn.addEventListener('click', function() {
    const isOpen = nav.classList.toggle('mobile-open');
    nav.style.display = isOpen ? 'flex' : '';
    nav.style.position = isOpen ? 'absolute' : '';
    nav.style.top = isOpen ? '70px' : '';
    nav.style.left = isOpen ? '0' : '';
    nav.style.right = isOpen ? '0' : '';
    nav.style.background = isOpen ? '#111' : '';
    nav.style.padding = isOpen ? '25px' : '';
    nav.style.flexDirection = isOpen ? 'column' : '';
    nav.style.alignItems = isOpen ? 'flex-start' : '';
  });

});