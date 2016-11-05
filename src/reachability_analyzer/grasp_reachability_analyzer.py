
import message_utils
import rospy

import moveit_msgs.msg
import geometry_msgs.msg
import actionlib
import moveit_commander
import tf


class GraspReachabilityAnalyzer():

    def __init__(self, move_group, grasp_approach_tran_frame, planner_id):
        """
        :type move_group: moveit_commander.MoveGroupCommander
        """
        self.pick_plan_client = actionlib.SimpleActionClient('/pickup', moveit_msgs.msg.PickupAction)
        self.move_group = move_group
        self.planner_id = planner_id
        self.grasp_approach_tran_frame = grasp_approach_tran_frame
        self.listener = tf.TransformListener()

    def publish_grasp_tf(self, pose_stamped, frame_name):
        pose = pose_stamped.pose
        br = tf.TransformBroadcaster()
        br.sendTransform((pose.position.x, pose.position.y, pose.position.z),
                     (pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w),
                     rospy.Time.now(),
                     frame_name,
                     pose_stamped.header.frame_id)

    def send_pick_request(self, pickup_goal):

        success = False
        received_result = False
        self.pick_plan_client.send_goal(pickup_goal)

        received_result = self.pick_plan_client.wait_for_result(rospy.Duration(rospy.get_param('~allowed_planning_time', 5)))

        if received_result:
            result = self.pick_plan_client.get_result()
            rospy.loginfo("result: " + str(result))
            success = result.error_code.val == result.error_code.SUCCESS
        else:
            result = None
            success = False

        rospy.loginfo("success of pick_plan_client:" + str(success))

        return success, result

    def query_moveit_for_reachability(self, graspit_grasp_msg):
        """
        :type graspit_grasp_msg: graspit_msgs.msg.Grasp
        """
        # self.move_group.set_planning_time(rospy.get_param('~allowed_planning_time'))

        moveit_grasp_msg = message_utils.graspit_grasp_to_moveit_grasp(graspit_grasp_msg,                                                                       
                                                                       self.move_group,
                                                                       self.listener,
                                                                       self.grasp_approach_tran_frame)
        rospy.loginfo("moveit_grasp_msg: " + str(moveit_grasp_msg))
        


        pickup_goal = message_utils.build_pickup_goal(moveit_grasp_msg=moveit_grasp_msg,
                                                      object_name=graspit_grasp_msg.object_name,
                                                      planning_group=self.move_group)

        rospy.loginfo("pickup_goal: " + str(pickup_goal))

        received_result = False
        success  = False
        try:
            self.pick_plan_client.wait_for_server(rospy.Duration(3))
            pickup_goal.planner_id = self.planner_id

            #publish where the moveit grasp is
            grasp_pose_stamped = pickup_goal.possible_grasps[0].grasp_pose
            self.publish_grasp_tf(grasp_pose_stamped, "grasp_moveit")

            #publish where teh graspit grasp is
            grasp_pose_stamped_1 = geometry_msgs.msg.PoseStamped()
            grasp_pose_stamped_1.header.frame_id= graspit_grasp_msg.object_name
            grasp_pose_stamped_1.pose = graspit_grasp_msg.final_grasp_pose
            self.publish_grasp_tf(grasp_pose_stamped_1, "grasp_graspit")

            #remove trajectory points for fingers because they are causing all reachability
            #checks to fail, this should be revisited at some point.
            pickup_goal.possible_grasps[0].pre_grasp_posture.points = []
            pickup_goal.possible_grasps[0].grasp_posture.points = []

            success, result = self.send_pick_request(pickup_goal)

        except Exception as e:
            rospy.logerr("failed to reach pick action server with err: %s" % e.message)


        return success, result