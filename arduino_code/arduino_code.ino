
//#include <Servo.h>

#include "stepper_driver.h"

// Comment this line to exclude prints, making things a little faster
// (though, idk, maybe not to an extent that matters, or maybe not enough.
// fuck.)
//#define PRINT_STUFF

const uint8_t servo_pin = 2;

StepperDriver stepper_driver;
//Servo servo;

int pos = 0;

float read_float() {
  union u_tag {
    byte b[4];
    float floatval;
  } u;

  while (Serial.available() < 4) { }

  u.b[0] = Serial.read();
  u.b[1] = Serial.read();
  u.b[2] = Serial.read();
  u.b[3] = Serial.read();

  return u.floatval;
}


const float gear_ratio = 2.4;
/*
float deg = 0;
void rotate(float deg_increm) {
  deg = deg + deg_increm;
*/
void rotate(float deg) {
  /*
  Serial.println(deg);
  Serial.println(deg * gear_ratio);
  Serial.println(stepper_driver.degree_to_microstep(deg * gear_ratio));
  Serial.println(long(stepper_driver.degree_to_microstep(deg * gear_ratio)));
  */
  stepper_driver.move_to(deg * gear_ratio);
  stepper_driver.busy_wait();
}


/*
int servo_pos = 0;
void init_servo() {
  //servo.write(servo_pos);
  //delay(2700);
  for (int pos = 180; pos > 0; pos--) {
    servo.write(pos);
    delay(15);
  }
}


void lineate(float mm_pos) {
  // Way we calculated this conversion factor:
  // 1) Found arguments to the servo.write fn (going through the loop below),
  // that did not make the servo behave weird. (40 and 150)
  // 2) (150 - 40) / (effective mm stroke given those arguments)
  // !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  // !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  // To make this accurate, we need to measure the denominator, if not crystal
  // clear what relationship between servo.write argument and position is from
  // docs.
  // !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  // !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  // 3) for now, we are estimating denominator to be 1cm
  int target_servo_pos = 40 + round(mm_pos * 9);

  if (target_servo_pos < 40) {
    target_servo_pos = 40;
  } else if (target_servo_pos > 150) {
    target_servo_pos = 150;
  }

  int servo_step;
  if (target_servo_pos >= servo_pos) {
    servo_step = 1;
  } else {
    servo_step = -1;
  }

  
  //for (int pos = servo_pos; pos != target_servo_pos; pos += servo_step) {
  //  servo.write(pos);
  //  delay(15);
  //}
  //servo.write(target_servo_pos);
  //delay(15);
  //servo_pos = target_servo_pos;
  
  servo.write(target_servo_pos);
}
*/


void setup() {
  Serial.begin(38400);
  Serial.println("start of setup");

  stepper_driver = StepperDriver(0, 10, 7, 8);
  stepper_driver.initialize();
  stepper_driver.set_fullstep_per_rev(400);
  stepper_driver.set_oc_threshold(String("OC_2250mA"));
  stepper_driver.set_jog_speed(50.0);
  stepper_driver.set_jog_acceleration(100.0);
  stepper_driver.set_jog_deceleration(100.0);
  stepper_driver.set_max_speed(500.0);
  stepper_driver.set_max_acceleration(1000.0);
  stepper_driver.set_max_deceleration(1000.0);
  stepper_driver.set_movement_params_to_jog();

  stepper_driver.enable();

  stepper_driver.set_position(0.0);
  
  // Attach the servo to the servo pin
  //servo.attach(servo_pin);

  // may need to uncomment for some bizarre reason
  //init_servo();
  Serial.println("end of setup");
}

void loop() {
  Serial.println("start of loop");

  rotate(0.0);
  Serial.println(stepper_driver.get_position());
  Serial.println(stepper_driver.get_position_fullsteps());
  Serial.println(stepper_driver.get_position_microsteps());
  delay(2000);
  rotate(180.0);  
  Serial.println(stepper_driver.get_position());
  Serial.println(stepper_driver.get_position_fullsteps());
  Serial.println(stepper_driver.get_position_microsteps());

  /*
  // This required moving these from protected section in .h file.
  Serial.println("conversion constants:");
  Serial.println("fullstep_per_rev:");
  Serial.println(stepper_driver.fullstep_per_rev_);
  Serial.println("fullstep_per_degree:");
  Serial.println(stepper_driver.fullstep_per_degree_);
  Serial.println("microstep_per_degree:");
  Serial.println(stepper_driver.microstep_per_degree_);
  Serial.println("degree_per_fullstep:");
  Serial.println(stepper_driver.degree_per_fullstep_);
  Serial.println("degree_per_microstep:");
  Serial.println(stepper_driver.degree_per_microstep_);
  Serial.println("");
  */
  
  delay(2000);
  rotate(-90.0);  
  Serial.println(stepper_driver.get_position());
  Serial.println(stepper_driver.get_position_fullsteps());
  Serial.println(stepper_driver.get_position_microsteps());
  delay(2000);
  
  /*
  #ifdef PRINT_STUFF
  Serial.println("reading linear actuator move position");
  #endif
  
  float curr_mm = read_float();
  
  #ifdef PRINT_STUFF
  Serial.println("reading stepper move amount");
  #endif
  
  float curr_deg_increm = read_float();
  
  #ifdef PRINT_STUFF
  Serial.println("moving linear actuator to:");
  Serial.println(curr_mm);
  #endif
  
  lineate(curr_mm);
  
  #ifdef PRINT_STUFF
  Serial.println("moving stepper motor by:");
  Serial.println(curr_deg_increm);
  #endif
  
  rotate(curr_deg_increm);
  Serial.println("ok");
  */
}
