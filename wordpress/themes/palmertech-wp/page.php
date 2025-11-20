<?php
/**
 * Default page template retaining global layout.
 *
 * @package Palmertech WP
 */

global $post;
get_header();
?>
<section class="page-content">
    <div class="container">
        <?php
        while (have_posts()) :
            the_post();
            echo '<h1 class="page-title">' . esc_html(get_the_title()) . '</h1>';
            echo '<div class="page-body">' . wp_kses_post(get_the_content()) . '</div>';
        endwhile;
        ?>
    </div>
</section>
<?php get_footer(); ?>
