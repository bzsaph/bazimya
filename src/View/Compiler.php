<?php

declare(strict_types=1);

namespace Bazimya\View;

/**
 * Compiles Bazimya templates into plain PHP.
 *
 * Supported syntax:
 *
 *   {{ $name }}              escaped echo
 *   {!! $html !!}            raw echo
 *   {{-- comment --}}        stripped
 *   @if / @elseif / @else / @endif
 *   @foreach / @endforeach
 *   @for / @endfor
 *   @while / @endwhile
 *   @break / @continue
 *   @php ... @endphp
 *   @extends('layouts.app')
 *   @section('body') ... @endsection
 *   @yield('body')
 *   @include('partials.nav')
 *   @include('partials.nav', ['key' => 'value'])
 */
class Compiler
{
    /** Directives that take a parenthesised expression. */
    protected const BLOCK_OPENERS = ['if', 'elseif', 'foreach', 'for', 'while'];

    public function compile(string $source): string
    {
        $source = $this->compileComments($source);
        $source = $this->compileRawPhp($source);
        $source = $this->compileLayoutDirectives($source);
        $source = $this->compileStructures($source);

        return $this->compileEchoes($source);
    }

    protected function compileComments(string $source): string
    {
        return (string) preg_replace('/\{\{--.*?--\}\}/s', '', $source);
    }

    protected function compileRawPhp(string $source): string
    {
        return (string) preg_replace('/@php(.*?)@endphp/s', '<?php$1?>', $source);
    }

    protected function compileLayoutDirectives(string $source): string
    {
        $source = (string) preg_replace_callback(
            '/@extends\s*\(/',
            fn (): string => '<?php $__view->extend(',
            $source,
        );
        $source = $this->closeCall($source, '$__view->extend(');

        $source = (string) preg_replace_callback(
            '/@section\s*\(/',
            fn (): string => '<?php $__view->startSection(',
            $source,
        );
        $source = $this->closeCall($source, '$__view->startSection(');

        $source = str_replace('@endsection', '<?php $__view->stopSection(); ?>', $source);
        $source = str_replace('@show', '<?php echo $__view->yieldSection($__view->stopSection()); ?>', $source);

        $source = (string) preg_replace('/@yield\s*\((.*?)\)/', '<?= $__view->yieldSection($1) ?>', $source);

        // Spread lets a single compiled form serve both @include('x') and
        // @include('x', [...]) without argument-order gymnastics.
        $source = (string) preg_replace(
            '/@include\s*\((.*?)\)\s*$/m',
            '<?= $__view->includeView($__data, ...[$1]) ?>',
            $source,
        );

        return (string) preg_replace(
            '/@include\s*\((.*?)\)/',
            '<?= $__view->includeView($__data, ...[$1]) ?>',
            $source,
        );
    }

    /**
     * Terminate a rewritten call that still has its original closing paren,
     * e.g. "<?php $__view->extend('layouts.app')" -> "...); ?>".
     */
    protected function closeCall(string $source, string $needle): string
    {
        $offset = 0;

        while (($start = strpos($source, $needle, $offset)) !== false) {
            $cursor = $start + strlen($needle);
            $depth = 1;
            $length = strlen($source);

            while ($cursor < $length && $depth > 0) {
                $char = $source[$cursor];

                if ($char === '(') {
                    $depth++;
                } elseif ($char === ')') {
                    $depth--;
                    if ($depth === 0) {
                        break;
                    }
                } elseif ($char === "'" || $char === '"') {
                    $cursor = $this->skipString($source, $cursor);
                }

                $cursor++;
            }

            $insertAt = $cursor + 1;
            $source = substr($source, 0, $insertAt) . '; ?>' . substr($source, $insertAt);
            $offset = $insertAt + 4;
        }

        return $source;
    }

    /** Advance past a quoted string, honouring backslash escapes. */
    protected function skipString(string $source, int $cursor): int
    {
        $quote = $source[$cursor];
        $length = strlen($source);
        $cursor++;

        while ($cursor < $length) {
            if ($source[$cursor] === '\\') {
                $cursor += 2;
                continue;
            }
            if ($source[$cursor] === $quote) {
                return $cursor;
            }
            $cursor++;
        }

        return $cursor;
    }

    protected function compileStructures(string $source): string
    {
        foreach (self::BLOCK_OPENERS as $directive) {
            $source = (string) preg_replace_callback(
                '/@' . $directive . '\s*\(/',
                fn (): string => '<?php ' . $directive . ' (',
                $source,
            );
            $source = $this->closeStructure($source, '<?php ' . $directive . ' (');
        }

        $replacements = [
            '@else'         => '<?php else: ?>',
            '@endif'        => '<?php endif; ?>',
            '@endforeach'   => '<?php endforeach; ?>',
            '@endfor'       => '<?php endfor; ?>',
            '@endwhile'     => '<?php endwhile; ?>',
            '@break'        => '<?php break; ?>',
            '@continue'     => '<?php continue; ?>',
        ];

        foreach ($replacements as $directive => $php) {
            $source = str_replace($directive, $php, $source);
        }

        return $source;
    }

    /**
     * Close a control structure with ": ?>" rather than "; ?>".
     */
    protected function closeStructure(string $source, string $needle): string
    {
        $offset = 0;

        while (($start = strpos($source, $needle, $offset)) !== false) {
            $cursor = $start + strlen($needle);
            $depth = 1;
            $length = strlen($source);

            while ($cursor < $length && $depth > 0) {
                $char = $source[$cursor];

                if ($char === '(') {
                    $depth++;
                } elseif ($char === ')') {
                    $depth--;
                    if ($depth === 0) {
                        break;
                    }
                } elseif ($char === "'" || $char === '"') {
                    $cursor = $this->skipString($source, $cursor);
                }

                $cursor++;
            }

            $insertAt = $cursor + 1;
            $source = substr($source, 0, $insertAt) . ': ?>' . substr($source, $insertAt);
            $offset = $insertAt + 4;
        }

        return $source;
    }

    protected function compileEchoes(string $source): string
    {
        $source = (string) preg_replace('/\{!!\s*(.+?)\s*!!\}/s', '<?= $1 ?>', $source);

        return (string) preg_replace('/\{\{\s*(.+?)\s*\}\}/s', '<?= $__view->e($1) ?>', $source);
    }
}
