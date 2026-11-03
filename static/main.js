// Wait for the DOM to load
document.addEventListener('DOMContentLoaded', function () {

  // ============================================================
  // HERO SLIDESHOW
  // ============================================================
  const heroImages = document.querySelectorAll('.hero-image');
  const heroNumber = document.querySelector('.hero-number');
  let currentSlide = 0;
  const totalSlides = heroImages.length;

  if (totalSlides > 0) {
    function showSlide(index) {
      heroImages.forEach(function (img, i) {
        if (i === index) {
          img.classList.add('active');
        } else {
          img.classList.remove('active');
        }
      });
      if (heroNumber) {
        var current = String(index + 1).padStart(2, '0');
        var total = String(totalSlides).padStart(2, '0');
        heroNumber.textContent = current + ' / ' + total;
      }
    }

    function nextSlide() {
      currentSlide = (currentSlide + 1) % totalSlides;
      showSlide(currentSlide);
    }

    showSlide(0);
    setInterval(nextSlide, 4000);
  }

  // ============================================================
  // SEARCH BAR
  // ============================================================
  const searchToggle = document.getElementById('search-toggle');
  const searchBar = document.getElementById('search-bar');
  const searchInput = document.getElementById('search-input');
  const searchForm = document.getElementById('search-form');
  const searchClose = document.getElementById('search-close');
  const noResultsDiv = document.getElementById('no-results');
  const categoryButtons = document.querySelectorAll('.category-btn');
  const products = document.querySelectorAll('.product');

  function filterProducts() {
    if (!searchInput) return;
    const query = searchInput.value.toLowerCase().trim();
    const activeBtn = document.querySelector('.category-btn.active');
    const activeCategory = activeBtn ? activeBtn.dataset.category : 'all';
    let visibleCount = 0;

    products.forEach(function (product) {
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

  function openSearch() {
    if (searchBar) {
      searchBar.style.display = 'block';
      if (searchInput) searchInput.focus();
    }
  }

  function closeSearch() {
    if (searchBar) {
      searchBar.style.display = 'none';
      if (searchInput) searchInput.value = '';
      filterProducts();
    }
  }

  if (searchToggle) {
    searchToggle.addEventListener('click', function (e) {
      e.preventDefault();
      if (searchBar.style.display === 'block') {
        closeSearch();
      } else {
        openSearch();
      }
    });
  }

  if (searchClose) {
    searchClose.addEventListener('click', function () {
      closeSearch();
    });
  }

  if (searchInput) {
    searchInput.addEventListener('input', filterProducts);
  }

  if (searchForm) {
    searchForm.addEventListener('submit', function (e) {
      e.preventDefault();
      filterProducts();
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && searchBar && searchBar.style.display === 'block') {
      closeSearch();
    }
  });

  // ============================================================
  // CATEGORY FILTER
  // ============================================================
  categoryButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      categoryButtons.forEach(function (btn) {
        btn.classList.remove('active');
      });
      this.classList.add('active');
      if (searchInput) searchInput.value = '';
      filterProducts();
    });
  });

  // ============================================================
  // MOBILE MENU
  // ============================================================
  const menuBtn = document.querySelector('.menu-btn');
  const nav = document.querySelector('.nav');

  if (menuBtn && nav) {
    menuBtn.addEventListener('click', function () {
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
  }

});