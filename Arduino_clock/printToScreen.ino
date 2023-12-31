
//printWhiteTime
void printWhiteTime() {
  display.clearDisplay();
  display.setTextColor( WHITE);
  display.setTextSize(2);
  display.setCursor(2, 0);
  display.print("Time:");
  if (time_white.hours < 10) {
    display.setCursor(2, (SCREEN_HEIGHT / 2) );
    display.print('0');
    display.print(time_white.hours);
    display.print(':');
  } else {
    display.print(time_white.hours);
    display.print(':');
  }

  if (time_white.minutes < 10) {
    display.setCursor(37, (SCREEN_HEIGHT / 2) );
    display.print('0');
    display.print(time_white.minutes);
    display.print(':');
  } else {
    display.print(time_white.minutes);
    display.print(':');
  }

  if (time_white.seconds < 10) {
    display.setCursor(72, (SCREEN_HEIGHT / 2) );
    display.print('0');
    display.print(time_white.seconds);
  } else {
    display.print(time_white.seconds);
  };
  display.display();
}



//printBlackTime
void printBlackTime() {
  display.clearDisplay();
  display.setTextColor( WHITE);
  display.setTextSize(2);
  display.setCursor(2, 0);
  display.print("Time:");
  if (time_black.hours < 10) {
    display.setCursor(2, (SCREEN_HEIGHT / 2) );
    display.print('0');
    display.print(time_black.hours);
    display.print(':');
  } else {
    display.print(time_black.hours);
    display.print(':');
  }

  if (time_black.minutes < 10) {
    display.setCursor(37, (SCREEN_HEIGHT / 2) );
    display.print('0');
    display.print(time_black.minutes);
    display.print(':');
  } else {
    display.print(time_black.minutes);
    display.print(':');
  }

  if (time_black.seconds < 10) {
    display.setCursor(72, (SCREEN_HEIGHT / 2) );
    display.print('0');
    display.print(time_black.seconds);
  } else {
    display.print(time_black.seconds);
  };
  display.display();
}
