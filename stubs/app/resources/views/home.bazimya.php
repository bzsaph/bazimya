@extends('layouts.app')

@section('title'){{ $title }}@endsection

@section('content')
    <p class="tag">It works</p>
    <h1>{{ $title }}</h1>

    @if (count($features) > 0)
        <p>Your application is running. Here is what is already wired up:</p>

        <ul>
            @foreach ($features as $feature)
                <li>{{ $feature }}</li>
            @endforeach
        </ul>

        <p style="margin-top:2rem">
            Edit <code>routes/web.php</code> to add routes, or run
            <code>bazimya make:controller PostController</code> to generate one.
        </p>
    @else
        <p>Edit <code>resources/views/home.bazimya.php</code> to change this page.</p>
    @endif
@endsection
