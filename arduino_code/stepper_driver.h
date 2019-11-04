#ifndef STEPPER_DRIVER_H
#define STEPPER_DRIVER_H
#include "SparkFunAutoDriver.h"

class StepperDriver
{
    public:

        static const int Degree_Per_Rev;

        // Default hardware parameters
        static const int Default_Board_Num;
        static const int Default_CS_Pin;
        static const int Default_Reset_Pin;
        static const int Default_Busy_Pin;
        static const int Default_Fullstep_Per_Rev;
        static const byte Default_Step_Mode;

        // Default current and kval parameters
        static const byte Default_Kval_Acceleration;
        static const byte Default_Kval_Deceleration;
        static const byte Default_Kval_Run;
        static const byte Default_Kval_Hold;
        static const String Default_OC_Threshold;

        // Default Movement parameters for jogging
        static const float Default_Jog_Speed;         // (deg/sec)
        static const float Default_Jog_Acceleration;  // (deg/sec^2)
        static const float Default_Jog_Deceleration;  // (deg/sec^2)

        // Default Movement parameters max values
        static const float Default_Max_Speed;         // (deg/sec)
        static const float Default_Max_Acceleration;  // (deg/sec^2)
        static const float Default_Max_Deceleration;  // (deg/sec^2)

        static const float Default_Full_Speed;        // (deg/sec) micro to full step transistion

        StepperDriver();
        StepperDriver(int board_num, int cs_pin, int reset_pin, int busy_pin);

        void initialize();

        // Driver info
        // ---------------------------------------------------------------------------------------
        void print_kval();
        void print_overcurrent_threshold();

        // Setter & Getters for hardware parameters
        // ----------------------------------------------------------------------------------------
        // Set board_num before initialization - if you aren't using defaults
        void set_board_num(int board_num);
        int get_board_num();   

        // Set cs_pin before initialization - if you aren't using defaults
        void set_cs_pin(int cs_pin);
        int get_cs_pin();      

        // Set reset_pin before initialization - if you aren't using defaults
        void set_reset_pin(int reset_pin);
        int get_reset_pin();   

        // Set busy_pin before initialization - if you aren't using defaults
        void set_busy_pin(int busy_pin);
        int get_busy_pin();    

        void set_fullstep_per_rev(int fullstep_per_rev);
        int get_fullstep_per_rev();

        bool set_step_mode(byte step_mode);
        byte get_step_mode();

        bool set_step_mode(String step_mode_string);
        String get_step_mode_string();

        void set_acceleration_kval(byte kval);
        byte get_acceleration_kval();

        void set_deceleration_kval(byte kval);
        byte get_deceleration_kval();

        void set_run_kval(byte kval);
        byte get_run_kval();

        void set_hold_kval(byte kval);
        byte get_hold_kval();

        bool set_oc_threshold(String threshold_string);
        String get_oc_threshold();

        // Setter & Getters for motion parameters
        // ----------------------------------------------------------------------------------------
        void set_jog_speed(float speed);
        float get_jog_speed();

        void set_jog_acceleration(float acceleration);
        float get_jog_acceleration();

        void set_jog_deceleration(float deceleration);
        float get_jog_deceleration();

        void set_max_speed(float speed);
        float get_max_speed();

        void set_max_acceleration(float acceleration);
        float get_max_acceleration();

        void set_max_deceleration(float deceleration);
        float get_max_deceleration();

        // Motion methods
        // ----------------------------------------------------------------------------------------
        void set_movement_params_to_jog();
        void set_movement_params_to_max();

        void run(float velocity);
        void run_fullsteps(float velocity);
        void run_microsteps(float velocity);

        void move_to_zero();
        void move_to(float pos);
        void move_to_fullsteps(float pos);
        void move_to_microsteps(long pos);

        bool is_busy();
        void busy_wait();

        float get_position();
        void set_position(float pos);

        float get_position_fullsteps();
        long get_position_microsteps();

        void soft_stop();
        void hard_stop();

        void release();
        void enable();
        bool is_enabled();

        void reset();


    protected:

        // State parameters
        bool enabled_;

        // Hardware parameters
        int board_num_;
        int cs_pin_;
        int reset_pin_;
        int busy_pin_;
        byte step_mode_;

        // Conversion constants
        long fullstep_per_rev_;
        float fullstep_per_degree_;
        float microstep_per_degree_;
        float degree_per_fullstep_;
        float degree_per_microstep_;

        // AutoDriver SPI interface 
        AutoDriver *driver_ptr_;

        // Jog movement parameters (units deg/sec, dec/sec^2)
        float jog_speed_;
        float jog_acceleration_;
        float jog_deceleration_;

        // Max movement parameters (units deg/sec, dec/sec^2)
        float max_speed_; 
        float max_acceleration_;
        float max_deceleration_;

        // Utility methods
        int microstep_per_fullstep(byte step_mode);
        float degree_to_fullstep(float value_fullstep);
        float degree_to_microstep(float value_fullstep);
        float fullstep_to_degree(float value_degree);
        float microstep_to_degree(float value_degree);
        void update_conversion_constants();



};


// Utility functions
// ------------------------------------------------------------------------------------------------

bool get_step_mode_from_string(String step_mode_string, byte &step_mode);
String get_string_from_step_mode(byte step_mode);
String get_string_from_oc_threshold(byte thresh);
byte get_oc_threshold_from_string(String thresh_string, bool &ok);



#endif
