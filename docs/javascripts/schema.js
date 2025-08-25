// Schema.org structured data for YokedCache
(function () {
    const schemaData = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "YokedCache",
        "description": "High-performance Python caching library with Redis auto-invalidation, vector search caching, and seamless FastAPI integration",
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Linux, macOS, Windows",
        "programmingLanguage": "Python",
        "author": {
            "@type": "Organization",
            "name": "Project Yoked LLC",
            "url": "https://github.com/sirstig"
        },
        "url": "https://sirstig.github.io/yokedcache",
        "downloadUrl": "https://pypi.org/project/yokedcache/",
        "codeRepository": "https://github.com/sirstig/yokedcache",
        "license": "https://opensource.org/licenses/MIT",
        "keywords": [
            "python caching library",
            "fastapi caching",
            "redis caching",
            "cache auto-invalidation",
            "vector search caching",
            "python redis",
            "fastapi redis",
            "intelligent caching",
            "database caching",
            "async caching"
        ],
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "USD"
        },
        "softwareVersion": "0.2.1",
        "requirements": "Python 3.9+",
        "featureList": [
            "Redis caching with auto-invalidation",
            "FastAPI integration",
            "Vector search caching",
            "Multi-backend support (Redis, Memcached, Memory)",
            "Production monitoring with Prometheus and StatsD",
            "Circuit breaker pattern for reliability",
            "Intelligent cache invalidation",
            "SQLAlchemy ORM support"
        ],
        "applicationSubCategory": "Python Library",
        "screenshot": "https://sirstig.github.io/yokedcache/assets/yokedcache-screenshot.png"
    };

    // Additional WebSite schema
    const websiteSchema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "YokedCache Documentation",
        "description": "Complete documentation for YokedCache, the Python caching library for FastAPI with Redis auto-invalidation",
        "url": "https://sirstig.github.io/yokedcache",
        "potentialAction": {
            "@type": "SearchAction",
            "target": "https://sirstig.github.io/yokedcache/search/?q={search_term_string}",
            "query-input": "required name=search_term_string"
        },
        "publisher": {
            "@type": "Organization",
            "name": "Project Yoked LLC",
            "url": "https://github.com/sirstig"
        }
    };

    // Documentation schema
    const docSchema = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": "YokedCache - Python Caching Library for FastAPI Documentation",
        "description": "Comprehensive documentation for implementing Redis caching in FastAPI applications with automatic invalidation and vector search",
        "author": {
            "@type": "Organization",
            "name": "Project Yoked LLC"
        },
        "datePublished": "2025-08-25",
        "dateModified": new Date().toISOString().split('T')[0],
        "publisher": {
            "@type": "Organization",
            "name": "Project Yoked LLC",
            "url": "https://github.com/sirstig"
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": "https://sirstig.github.io/yokedcache"
        }
    };

    // Insert schema data
    function insertSchema(schema, id) {
        const script = document.createElement('script');
        script.type = 'application/ld+json';
        script.id = id;
        script.textContent = JSON.stringify(schema);
        document.head.appendChild(script);
    }

    // Add all schemas when DOM is ready
    document.addEventListener('DOMContentLoaded', function () {
        insertSchema(schemaData, 'software-schema');
        insertSchema(websiteSchema, 'website-schema');
        insertSchema(docSchema, 'documentation-schema');
    });
})();
