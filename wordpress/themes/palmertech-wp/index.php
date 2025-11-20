<?php
/**
 * Fallback index template to satisfy WordPress theme requirements.
 *
 * @package Palmertech WP
 */

global $post;
get_header();
?>
<section class="page-content">
    <div class="container">
        <?php if (have_posts()) : ?>
            <?php while (have_posts()) : the_post(); ?>
                <article id="post-<?php the_ID(); ?>" <?php post_class('post-card'); ?>>
                    <h2 class="page-title"><a href="<?php the_permalink(); ?>"><?php the_title(); ?></a></h2>
                    <div class="page-body"><?php the_excerpt(); ?></div>
                </article>
            <?php endwhile; ?>
            <?php the_posts_navigation(); ?>
        <?php else : ?>
            <p><?php esc_html_e('No content available yet. Create a page or post to get started.', 'palmertech-wp'); ?></p>
        <?php endif; ?>
    </div>
</section>
<?php get_footer(); ?>
