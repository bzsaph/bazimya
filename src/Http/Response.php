<?php

declare(strict_types=1);

namespace Bazimya\Http;

use Bazimya\Foundation\Application;

class Response
{
    public function __construct(
        protected string $content = '',
        protected int $status = 200,
        protected array $headers = [],
    ) {
    }

    public static function make(string $content = '', int $status = 200, array $headers = []): static
    {
        return new static($content, $status, $headers);
    }

    public static function json(mixed $data, int $status = 200, array $headers = []): static
    {
        return new static(
            json_encode($data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) ?: 'null',
            $status,
            array_merge(['Content-Type' => 'application/json; charset=utf-8'], $headers),
        );
    }

    public static function redirect(string $to, int $status = 302): static
    {
        return new static('', $status, ['Location' => $to]);
    }

    /** Render a view into a response. */
    public static function view(string $view, array $data = [], int $status = 200): static
    {
        $rendered = Application::getInstance()->make('view')->render($view, $data);

        return new static($rendered, $status, ['Content-Type' => 'text/html; charset=utf-8']);
    }

    public function header(string $name, string $value): static
    {
        $this->headers[$name] = $value;

        return $this;
    }

    public function status(): int
    {
        return $this->status;
    }

    public function content(): string
    {
        return $this->content;
    }

    /** @return array<string, string> */
    public function headers(): array
    {
        return $this->headers;
    }

    public function send(): void
    {
        if (! headers_sent()) {
            http_response_code($this->status);

            if (! isset($this->headers['Content-Type']) && $this->content !== '') {
                $this->headers['Content-Type'] = 'text/html; charset=utf-8';
            }

            foreach ($this->headers as $name => $value) {
                header("{$name}: {$value}");
            }
        }

        echo $this->content;
    }
}
