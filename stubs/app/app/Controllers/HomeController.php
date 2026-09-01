<?php

declare(strict_types=1);

namespace App\Controllers;

use Bazimya\Facades\Python;
use Bazimya\Http\Controller;
use Bazimya\Http\Request;
use Bazimya\Http\Response;
use RuntimeException;

class HomeController extends Controller
{
    public function index(Request $request): Response
    {
        return $this->view('home', [
            'title' => 'Bazimya',
            'features' => [
                'Routing with named routes, groups and middleware',
                'Bazimya templates with layouts and sections',
                'Query builder, models and migrations',
                'Python services callable straight from PHP',
            ],
        ]);
    }

    public function greet(Request $request, ?string $name = null): Response
    {
        return $this->view('home', [
            'title' => 'Hello, ' . ($name ?? 'stranger'),
            'features' => [],
        ]);
    }

    public function python(Request $request): Response
    {
        try {
            $result = Python::call('ExampleService', [
                'message' => (string) $request->input('message', 'Hello from PHP'),
            ]);
        } catch (RuntimeException $e) {
            return $this->json([
                'ok' => false,
                'error' => $e->getMessage(),
            ], 500);
        }

        return $this->json([
            'ok' => true,
            'python' => $result,
        ]);
    }
}
