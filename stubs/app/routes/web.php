<?php

declare(strict_types=1);

use App\Controllers\HomeController;
use Bazimya\Facades\Route;
use Bazimya\Http\Request;

/*
 * Application routes.
 *
 * Actions can be a controller pair, a "Controller@method" string, or a closure.
 */

Route::get('/', [HomeController::class, 'index'])->name('home');

Route::get('/about', function (Request $request) {
    return 'Built with Bazimya.';
})->name('about');

// {name?} is optional — /hello and /hello/james both match.
Route::get('/hello/{name?}', [HomeController::class, 'greet'])->name('hello');

// Demonstrates the PHP -> Python bridge.
Route::get('/python', [HomeController::class, 'python'])->name('python');

Route::group(['prefix' => 'api'], function (): void {
    Route::get('/status', fn () => [
        'status' => 'ok',
        'framework' => 'Bazimya',
    ])->name('api.status');
});
