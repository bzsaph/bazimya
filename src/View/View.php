<?php

declare(strict_types=1);

namespace Bazimya\View;

use RuntimeException;
use Throwable;

/**
 * Locates, compiles and renders Bazimya templates.
 *
 * Templates live in resources/views and end in .bazimya.php. Compiled output
 * is cached in storage/framework/views and refreshed when the source changes.
 */
class View
{
    protected Compiler $compiler;

    /** @var array<string, string> Captured @section content. */
    protected array $sections = [];

    /** @var array<int, string> Names of sections currently being captured. */
    protected array $sectionStack = [];

    /** @var array<int, string|null> Parent layout per nested render(). */
    protected array $parentStack = [];

    /** @var array<string, mixed> Data shared with every view. */
    protected array $shared = [];

    public function __construct(
        protected string $viewPath,
        protected string $cachePath,
    ) {
        $this->compiler = new Compiler();
    }

    public function share(string $key, mixed $value): void
    {
        $this->shared[$key] = $value;
    }

    public function exists(string $view): bool
    {
        return is_file($this->resolvePath($view));
    }

    public function resolvePath(string $view): string
    {
        $relative = str_replace('.', '/', $view);

        return rtrim($this->viewPath, '/') . '/' . $relative . '.bazimya.php';
    }

    /**
     * Render a view, then render its layout if it declared @extends.
     *
     * @param array<string, mixed> $data
     */
    public function render(string $view, array $data = []): string
    {
        $path = $this->resolvePath($view);

        if (! is_file($path)) {
            throw new RuntimeException("View [{$view}] not found at {$path}");
        }

        $data = array_merge($this->shared, $data);

        $this->parentStack[] = null;

        $content = $this->evaluate($this->compiled($path), $data);

        $parent = array_pop($this->parentStack);

        if ($parent !== null) {
            // Sections captured by the child are still in $this->sections, so
            // the layout's @yield calls can pick them up.
            return $this->render($parent, $data);
        }

        return $content;
    }

    /**
     * Compile the template if the cache is missing or stale, and return the
     * path to the compiled PHP file.
     */
    protected function compiled(string $path): string
    {
        if (! is_dir($this->cachePath)) {
            mkdir($this->cachePath, 0775, true);
        }

        $cacheFile = rtrim($this->cachePath, '/') . '/' . md5($path) . '.php';

        if (! is_file($cacheFile) || filemtime($path) > filemtime($cacheFile)) {
            $source = file_get_contents($path);

            if ($source === false) {
                throw new RuntimeException("Unable to read view at {$path}");
            }

            file_put_contents($cacheFile, $this->compiler->compile($source));
        }

        return $cacheFile;
    }

    /**
     * @param array<string, mixed> $data
     */
    protected function evaluate(string $compiledFile, array $data): string
    {
        $__view = $this;
        $__data = $data;

        extract($data, EXTR_SKIP);

        ob_start();

        try {
            include $compiledFile;
        } catch (Throwable $e) {
            ob_end_clean();
            throw $e;
        }

        return (string) ob_get_clean();
    }

    /* ---------------------------------------------------------------------
     | Directive runtime — called from compiled templates
     * ------------------------------------------------------------------ */

    public function e(mixed $value): string
    {
        if ($value === null) {
            return '';
        }

        if (is_array($value) || (is_object($value) && ! method_exists($value, '__toString'))) {
            return htmlspecialchars(
                (string) json_encode($value, JSON_UNESCAPED_SLASHES),
                ENT_QUOTES,
                'UTF-8',
            );
        }

        return htmlspecialchars((string) $value, ENT_QUOTES, 'UTF-8');
    }

    public function extend(string $layout): void
    {
        if ($this->parentStack === []) {
            $this->parentStack[] = $layout;

            return;
        }

        $this->parentStack[array_key_last($this->parentStack)] = $layout;
    }

    public function startSection(string $name, ?string $content = null): void
    {
        if ($content !== null) {
            $this->sections[$name] = $content;

            return;
        }

        $this->sectionStack[] = $name;
        ob_start();
    }

    public function stopSection(): string
    {
        if ($this->sectionStack === []) {
            throw new RuntimeException('@endsection without a matching @section.');
        }

        $name = array_pop($this->sectionStack);
        $this->sections[$name] = (string) ob_get_clean();

        return $name;
    }

    public function yieldSection(string $name, string $default = ''): string
    {
        return $this->sections[$name] ?? $default;
    }

    /**
     * @param array<string, mixed> $base  Data from the including template.
     * @param array<string, mixed> $extra Extra data passed to @include.
     */
    public function includeView(array $base, string $view, array $extra = []): string
    {
        return $this->render($view, array_merge($base, $extra));
    }

    public function clearCache(): int
    {
        if (! is_dir($this->cachePath)) {
            return 0;
        }

        $cleared = 0;

        foreach (glob(rtrim($this->cachePath, '/') . '/*.php') ?: [] as $file) {
            if (unlink($file)) {
                $cleared++;
            }
        }

        return $cleared;
    }
}
