package com.maimai.dx;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;

/** 入口：一个全屏、常亮、横屏的 GameView。就这么一个 Activity。 */
public class MainActivity extends Activity {

    private GameView game;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Window w = getWindow();
        w.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        w.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
        w.setStatusBarColor(Color.rgb(5, 8, 12));
        w.setNavigationBarColor(Color.rgb(5, 8, 12));

        game = new GameView(this);
        setContentView(game);
        immersive();
    }

    private void immersive() {
        int f = View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION;
        getWindow().getDecorView().setSystemUiVisibility(f);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) immersive();
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (game != null) game.audio.stop();
    }

    @Override
    protected void onResume() {
        super.onResume();
        immersive();
    }

    @Override
    public void onBackPressed() {
        if (game == null) { super.onBackPressed(); return; }
        switch (game.scene) {
            case GameView.SCENE_PLAY:
            case GameView.SCENE_RESULT:
                game.backToSelect();
                break;
            case GameView.SCENE_SELECT:
            case GameView.SCENE_SCORES:
            case GameView.SCENE_SET:
                game.goHome();
                break;
            default:
                super.onBackPressed();
                break;
        }
    }
}
