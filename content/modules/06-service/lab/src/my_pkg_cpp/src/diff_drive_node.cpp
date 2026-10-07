#include <chrono>
#include <cmath>
#include <memory>

#include "geometry_msgs/msg/twist.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "rclcpp/rclcpp.hpp"

using namespace std::chrono_literals;

// Robot à conduite différentielle simulé : /cmd_vel → position → /odom.
class DiffDriveNode : public rclcpp::Node
{
public:
  DiffDriveNode()
  : Node("diff_drive_node")
  {
    cmd_sub_ = create_subscription<geometry_msgs::msg::Twist>(
      "cmd_vel", 10,
      [this](const geometry_msgs::msg::Twist & msg) {
        v_ = msg.linear.x;
        w_ = msg.angular.z;
      });
    odom_pub_ = create_publisher<nav_msgs::msg::Odometry>("odom", 10);
    timer_ = create_wall_timer(50ms, [this]() {update();});
    RCLCPP_INFO(get_logger(), "diff_drive_node prêt : commandes sur /cmd_vel, position sur /odom");
  }

private:
  void move_robot(double v, double w, double dt)
  {
    theta_ = std::atan2(std::sin(theta_ + w * dt), std::cos(theta_ + w * dt));
    x_ += v * std::cos(theta_) * dt;
    y_ += v * std::sin(theta_) * dt;
  }

  void update()
  {
    move_robot(v_, w_, dt_);
    nav_msgs::msg::Odometry odom;
    odom.header.stamp = now();
    odom.header.frame_id = "odom";
    odom.child_frame_id = "base_link";
    odom.pose.pose.position.x = x_;
    odom.pose.pose.position.y = y_;
    odom.pose.pose.orientation.z = std::sin(theta_ / 2);
    odom.pose.pose.orientation.w = std::cos(theta_ / 2);
    odom.twist.twist.linear.x = v_;
    odom.twist.twist.angular.z = w_;
    odom_pub_->publish(odom);
  }

  double x_ = 0.0, y_ = 0.0, theta_ = 0.0;
  double v_ = 0.0, w_ = 0.0;
  const double dt_ = 0.05;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_sub_;
  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odom_pub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<DiffDriveNode>());
  rclcpp::shutdown();
  return 0;
}
